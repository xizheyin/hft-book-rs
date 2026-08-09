# 高性能日志 (Logging)

日志不是一种东西。订单审计事件、程序诊断日志和聚合指标的可靠性要求不同；只有先分类，才能回答“队列满了能不能丢”。

## 1. 三类记录，三种策略

| 类型 | 例子 | 丢失策略 | 典型用途 |
| --- | --- | --- | --- |
| 审计/业务事件 | 订单意图、风控结果、实际发送、ACK、Fill、限额变更、人工操作 | 不得静默丢；无法可靠记录时通常阻止新的扩险动作 | 重放、对账、合规调查 |
| 诊断日志 | 连接重试、解析错误详情、调试上下文 | 可限速、采样或丢弃，但必须记录丢弃数量 | 排障 |
| 指标 | 计数器、队列水位、延迟分布 | 聚合或采样；标记数据缺口 | 告警、趋势和容量 |

“所有日志一条不能丢”和“队列满就全部丢”都不准确。策略应由事件类别、适用留存规则和故障模型决定。

> Kill/Cancel 通道通常要在审计存储异常时仍可用，因为它用于降低风险。可以停止 New，却不能因日志故障把减险能力一起锁死。

## 2. 异步日志并不免费

```mermaid
flowchart LR
    H["热路径生产者"] --> Q["有界事件队列"]
    Q --> W["日志消费者"]
    W --> J["带校验的本地 Journal"]
    J --> D["持久存储 / 复制"]
    Q -. "水位、丢弃、最老事件 age" .-> M["监控"]
```

异步化把格式化和 I/O 移出热路径，但生产者仍会承担：事件编码、拷贝、原子同步、缓存行争用和满队列处理。不能在没有硬件和负载口径时宣称“纳秒级”。

常见优化是：

- 预分配有界队列，避免热路径隐式扩容；
- 记录整数 ID、整数价格和原因码，后台再解析；
- SPSC 用于单生产者，MPSC 用于多生产者；
- 诊断文本使用静态模板 ID + 固定字段；
- 批量写可以提高吞吐，但会增加首条事件的等待时间。

### 2.1 固定事件不等于强行填满缓存行

```rust
#[derive(Debug, Clone, Copy)]
pub enum AuditEvent {
    OrderIntent {
        client_id: u64,
        instrument_id: u32,
        price_ticks: i64,
        quantity: u64,
    },
    RiskReject { client_id: u64, reason_code: u16 },
    Fill { execution_id: u64, client_id: u64, quantity: u64 },
}
```

不要凭猜测加 `_Padding([u8; N])` 声称正好 64 字节；枚举布局、对齐和目标平台都会影响大小。用 `size_of`、队列槽位布局和缓存计数器验证，且价格不要为方便格式化而使用浮点账本值。

## 3. 满队列策略必须写进 API

下面用标准库有界通道给出一份可编译的语义示例。真实系统可替换成经过验证的 SPSC/MPSC，但必须保留“失败时归还事件所有权”的 API 契约。

```rust
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::mpsc::{SyncSender, TrySendError};

#[derive(Debug, Clone, Copy)]
pub struct EncodedEvent {
    pub sequence: u64,
    pub event_type: u16,
}

pub struct EventSink {
    sender: SyncSender<EncodedEvent>,
    dropped_diagnostic: AtomicU64,
}

impl EventSink {
    fn try_push(&self, event: EncodedEvent) -> Result<(), EncodedEvent> {
        match self.sender.try_send(event) {
            Ok(()) => Ok(()),
            Err(TrySendError::Full(event) | TrySendError::Disconnected(event)) => Err(event),
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub enum EventClass { Audit, Diagnostic }

pub enum EmitResult {
    Enqueued,
    DiagnosticDropped,
    /// 把未入队事件交还调用者，供备用 journal 或安全停发流程使用。
    AuditUnavailable(EncodedEvent),
}

pub fn emit(
    sink: &EventSink,
    class: EventClass,
    event: EncodedEvent,
) -> EmitResult {
    let event = match sink.try_push(event) {
        Ok(()) => return EmitResult::Enqueued,
        Err(event) => event, // try_push 失败时必须归还所有权
    };

    match class {
        EventClass::Diagnostic => {
            sink.dropped_diagnostic.fetch_add(1, Ordering::Relaxed);
            EmitResult::DiagnosticDropped
        }
        EventClass::Audit => EmitResult::AuditUnavailable(event),
    }
}
```

调用者收到 `AuditUnavailable` 后应执行预先批准的安全策略，例如：

1. 将系统标记为 degraded；
2. 阻止新的普通订单，保留 Cancel/kill；
3. 告警并尝试备用 journal；
4. 保存“从哪个序号开始无法证明完整”的缺口；
5. 恢复后对账，未通过门禁前不自动恢复交易。

不要在队列满分支调用 `eprintln!`：它可能锁住 stderr、阻塞并形成递归日志风暴。满队列计数器应预先存在，告警由独立健康线程读取。

### 3.1 阻塞、丢弃还是停发？

| 行为 | 优点 | 风险 |
| --- | --- | --- |
| 阻塞生产者 | 审计事件不被主动丢弃 | 热路径停顿，可能错过行情 |
| 丢弃事件 | 保住生产者延迟 | 审计链不完整，不能用于关键业务事件 |
| 停止新单并排空 | 不继续制造不可审计副作用 | 可用性下降，需保留减险路径 |
| 切换备用 sink | 提高韧性 | 双写、顺序、去重和故障切换更复杂 |

无限增大队列只会延后持续过载。除了 depth，还要监控最老事件 age 和消费者落后序号。

## 4. 二进制日志要显式编码

不能把 Rust enum 的原始内存直接 `memcpy` 到文件并称为稳定格式，因为它可能包含 padding，布局也没有跨版本、跨平台保证。一个可恢复 journal 至少要定义：

```text
magic | schema_version | record_type | payload_len | sequence
event_time | receive_time | payload | checksum
```

还要说明：

- 字节序和整数缩放；
- schema 演进与未知字段；
- 部分写入和文件尾损坏如何截断；
- sequence/Client ID/execution ID 如何去重；
- `write`、page cache、`fsync`、设备缓存与复制 ACK 分别代表什么持久性；
- 密钥、个人信息和策略参数怎样脱敏与授权。

`mmap` 不等于已经持久化，`O_DIRECT` 也不是默认更快：它有对齐限制，会绕过 page cache 的一些帮助，并增加实现复杂度。两者都要在目标文件系统和设备故障模型下测试。

## 5. 时间戳

- 事件时间：交易所提供的外部时间；
- 接收/发送硬件时间：测量 wire 边界；
- 单调时间：本机持续时间和超时；
- 墙上时间：人类报表和跨系统关联。

`SystemTime::now()` 是否走系统调用取决于平台，不能简单说“一定慢”。TSC 读取成本可能较低，但必须验证跨核稳定性、频率语义、序列化要求和校准误差；裸 `_rdtsc()` 还是架构相关 `unsafe`。优先使用项目的统一时钟抽象，并记录时间质量。

## 6. 停机与崩溃恢复

正常停机需要：停止接收普通新事件、排空队列、写入终止序号、flush/按策略同步、等待消费者退出。不能只把 `running=false` 后立即丢掉队列尾部。

崩溃恢复要测试：

- 记录写到一半断电；
- checksum 错误和尾部截断；
- 同一批记录重放两次；
- 磁盘满、只读、I/O 卡顿和文件轮转；
- 主日志和备用日志不同步；
- 恢复后的订单/成交与独立 drop copy 对账。

## 7. 面试追问与验证清单

**日志队列满了怎么办？** 先问事件类别。诊断日志可采样并增加 dropped counter；关键审计事件不得静默丢，通常触发停止新单、保留撤单、切备用和对账。

**异步日志为何仍会影响 p99？** 队列 push 会写共享缓存行，满队列会背压，消费者还可能与热线程争 CPU、内存带宽或 I/O。

**二进制日志是否直接 dump struct？** 不应。要显式 schema、长度、版本、字节序和 checksum，保证跨版本解析和崩溃恢复。

验证清单：

- [ ] 每种事件有 owner、可靠性和留存等级；
- [ ] 队列高水位、满队列和最老 age 有指标；
- [ ] 诊断丢弃本身可观测；
- [ ] 审计不可用会阻止新单但保留减险；
- [ ] 峰值、持续过载、磁盘卡顿和崩溃恢复已演练；
- [ ] 解析器能读取旧 schema，损坏记录不会越界；
- [ ] 端到端 p50/p99 与开启/关闭日志的 A/B 结果已记录。

## 8. 做题方法：从序号连续性恢复日志

1. 先给记录格式画边界：固定头、版本、类型、长度、序号、payload、checksum。解析时先验证“剩余字节至少容纳头”，再验证长度上限和完整 payload，最后才读取字段。
2. 在头、payload、checksum 和批次 flush 之间分别截断文件。恢复程序只能接受最后一条完整且校验通过的记录，并把其后尾部截掉或隔离，不能越界猜测下一条。
3. 维护 `expected_sequence`。发现重复序号时按业务 ID 去重，发现跳号时记录明确缺口；不能因为文件之后还能解析就假装审计链完整。
4. 把 `write`、page cache、同步刷新和复制 ACK 标在时间线上。题目问崩溃后能恢复到哪里，就只承诺已经越过指定持久化边界的序号。
5. 队列满题先按诊断、业务事件、审计三类选择动作，再让 sink 长时间卡住。验算热路径是否递归写日志、审计缺口是否触发安全状态、恢复后是否与独立业务事实对账。

最终不变量是：每个已接受的关键副作用都有可定位的审计序号；任何无法证明连续的区间都会显式暴露，而不是静默跳过。

---

下一章：[配置热加载 (Configuration)](config.md)
