# 模糊测试与属性测试：让机器寻找你没想到的输入

示例测试会问：“输入 A，是否得到 B？”模糊测试（fuzzing）则让机器持续变异输入，寻找 panic、越界、死循环和规则破坏；属性测试（property-based testing）会生成大量结构化数据，检查一条永远应成立的性质。

HFT 系统非常适合这两种方法：它要处理不可信网络字节、复杂订单状态机、序列号回绕和大量数值边界。手工列十个案例，远远覆盖不了所有组合。

## 1. 四种方法不要混淆

| 方法 | 输入来源 | 主要寻找什么 | 典型工具 |
| :--- | :--- | :--- | :--- |
| 示例测试 | 人工指定 | 已知规则是否满足 | `#[test]` |
| 属性测试 | 按类型/约束生成 | 普遍不变量与边界组合 | `proptest` |
| Fuzz | 从种子不断变异 | 崩溃、挂起、解析漏洞、意外状态 | `cargo-fuzz` / libFuzzer |
| 并发模型检查 | 枚举调度与内存交错 | 数据竞争、错误内存序 | `loom` |

它们互相补充。Fuzz 跑一亿次也不等于证明没有 bug；属性写错了，测试只会非常努力地证明一条没价值的命题。

## 2. 好属性从业务不变量开始

最弱的 fuzz target 只是“别 panic”。这是必要条件，却不是交易正确性的充分条件。

### 2.1 常见属性清单

#### 编解码器

```text
decode(encode(message)) == message
```

注意比较的应是语义等价。有些协议允许不同但等价的字段顺序或 padding。

#### 订单簿

- 最优买价小于最优卖价，除非撮合过程允许短暂 crossed book。
- 每个价位聚合量等于该价位所有订单剩余量之和。
- 剩余数量永不为负，成交总量不超过原始数量。
- 删除不存在的订单返回明确错误，而不是损坏其他订单。

#### 风控

- `Allow` 的订单一定满足全部限制。
- 收紧限制不会把原本拒绝的订单变成允许（单调性，前提是其他输入相同）。
- 任何被拒绝的订单都不会到达发送出口。

#### 序列号与恢复

- 重复处理同一条幂等消息不会重复改变仓位。
- gap 被完整补齐后，状态等于按顺序处理所有消息的状态。
- 时间和已确认序列号不会倒退，除非协议显式定义回绕。

#### 数值

- 金额计算不溢出。
- ticks 与显示价格转换遵守明确舍入规则。
- 聚合后拆分、拆分后聚合保持数量守恒。

## 3. 用 `proptest` 写第一个属性测试

### 3.1 依赖

```toml
[dev-dependencies]
proptest = "1"
```

### 3.2 编解码往返

下面是依赖 `proptest` 和项目编解码器的**属性测试骨架**，其中 `Side`、`encode`、`decode` 由项目提供，因此不作为标准库 doctest。添加上面的 dev-dependency 并补齐领域类型后，运行 `cargo test order_codec_round_trip`；失败时保存 `proptest` 输出的最小反例与 seed。

```rust,ignore
use proptest::prelude::*;

#[derive(Debug, Clone, PartialEq, Eq)]
struct Order {
    id: u64,
    price_ticks: i64,
    qty: u32,
    side: Side,
}

prop_compose! {
    fn valid_order()
        (id in 1_u64..u64::MAX, price_ticks in 1_i64..10_000_000, qty in 1_u32..1_000_000,
         is_buy in any::<bool>())
        -> Order
    {
        Order {
            id,
            price_ticks,
            qty,
            side: if is_buy { Side::Buy } else { Side::Sell },
        }
    }
}

proptest! {
    #[test]
    fn order_codec_round_trip(order in valid_order()) {
        let bytes = encode(&order);
        let decoded = decode(&bytes).expect("encoder must create valid bytes");
        prop_assert_eq!(decoded, order);
    }
}
```

属性测试失败后，`proptest` 会 shrink（缩减）输入，例如把一个复杂订单缩成触发 bug 的最小价格或数量。这通常比保存一整天 PCAP 更容易定位问题。

### 3.3 不要生成大量“无效噪音”

如果 99.9% 输入都在第一行被拒绝，测试虽然跑了很多次，却没有深入状态机。应同时保留两类生成器：

- **合法生成器**：走深层业务逻辑，验证不变量。
- **任意字节/非法生成器**：验证解析器能安全拒绝异常输入。

尽量通过生成策略直接满足前置条件，而不是大量使用 `prop_assume!` 丢弃样本。丢弃率太高会降低覆盖效率。

## 4. 关系型属性比固定答案更强

有时很难为随机输入提前算出唯一答案，可以检查输入变换前后的关系。

### 4.1 变形测试（metamorphic testing）

例子：给所有买卖价格同时加上相同合法偏移，撮合的订单 ID 和数量关系应保持一致，只是成交价整体平移。

### 4.2 差分测试（differential testing）

让两个独立实现处理相同输入：

这段差分属性同样依赖 `proptest`、`event_sequence` 和两套项目实现。接入后用 `cargo test optimized_book_matches_reference` 单独验证，并确认 reference implementation 没有复用被测实现的关键逻辑。

```rust,ignore
proptest! {
    #[test]
    fn optimized_book_matches_reference(events in event_sequence()) {
        let fast = run_fast_book(&events);
        let simple = run_reference_book(&events);
        prop_assert_eq!(fast.observable_state(), simple.observable_state());
    }
}
```

reference implementation 可以很慢，但应尽量简单、明显正确。两边共享太多内部代码会形成共同盲区。

### 4.3 守恒关系

在没有外部资金流入时：

```text
买方成交数量 == 卖方成交数量
订单原始数量 == 已成交数量 + 剩余数量 + 已取消数量
```

守恒关系对一长串随机事件尤其有效，因为它不需要预先知道每一步的完整订单簿。

## 5. 用 `cargo-fuzz` 测任意网络字节

`cargo-fuzz` 使用 LLVM libFuzzer，根据覆盖反馈保留能探索新路径的输入。

### 5.1 初始化

```bash
cargo install cargo-fuzz
cargo fuzz init
cargo fuzz add parse_market_packet
```

它会创建独立的 `fuzz/` package，避免把 fuzz 依赖放进生产二进制。

### 5.2 最小 target：任意输入都不能失控

下面文件由 `cargo fuzz add parse_market_packet` 放入独立 `fuzz/` package，依赖 `libfuzzer_sys` 与项目解析 crate，不能作为普通 doctest。完成 target 后可用 `cargo fuzz run parse_market_packet -- -max_len=4096` 验证，并把工具版本和输入上限固定在 CI 配置中。

```rust,ignore
#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let result = market_protocol::parse_packet(data);

    if let Ok(packet) = result {
        // 成功解析时再检查更强的不变量。
        assert!(packet.encoded_len() <= data.len());
        assert!(packet.messages().all(|msg| msg.is_semantically_valid()));
    }
});
```

对任意 `data`，目标应满足：

- 不 panic、不越界、不触发未定义行为。
- 不无限循环，也不按输入声明分配无限内存。
- 失败返回结构化错误。
- 成功时满足协议和业务不变量。

### 5.3 限制资源放大

恶意头部可能声明“接下来有 4GB body”。解析器不能先分配 4GB 再检查输入是否足够。

推荐顺序：

1. 检查固定头部是否完整。
2. 解析长度并验证协议上限。
3. 使用 `checked_add` 计算边界。
4. 确认 slice 足够长。
5. 最后才分配或深入解析。

Fuzz 不仅找崩溃，也要给单次执行设置合理超时和最大输入长度，发现超线性算法、压缩炸弹和死循环。

## 6. 结构化 Fuzz：更快到达深层逻辑

纯随机字节很难同时满足 magic、版本、长度和校验和。可以让 fuzzer 先生成结构化消息，再编码为字节：

该 target 还需要启用 `arbitrary` 的 derive 支持，并依赖项目的 `normalize`、`encode`、`decode`。在 fuzz package 中补齐依赖后，使用 `cargo fuzz run <结构化_target名>` 单独运行；同时保留上一节的原始字节 target。

```rust,ignore
use arbitrary::Arbitrary;
use libfuzzer_sys::fuzz_target;

#[derive(Arbitrary, Debug)]
struct FuzzOrder {
    id: u32,
    price_ticks: i32,
    qty: u16,
    side: bool,
}

fuzz_target!(|input: FuzzOrder| {
    let message = normalize(input);
    let bytes = encode(&message);
    let decoded = decode(&bytes).expect("valid encoder output must decode");
    assert_eq!(decoded, message);
});
```

应同时保留“任意原始字节”和“合法结构体”两个 target：前者攻击解析边界，后者探索业务深处。

### 6.1 Dictionary 与种子语料

协议 dictionary 可以包含 magic、消息类型、分隔符和常见字段片段，帮助变异器更快构造近似有效消息。初始 corpus 可来自：

- 每种消息的最小合法样本。
- 曾经触发线上 bug 的脱敏输入。
- 不同协议版本和边界长度。
- gap、恢复、重复与乱序场景。

语料不应包含生产账户、策略参数、密钥或未经授权的交易所数据。

## 7. 状态机 Fuzz：输入是一串动作

许多交易 bug 单看一条消息不会出现，必须经过一段历史：

```text
New -> Ack -> PartialFill -> Cancel -> FinalFill -> CancelAck
```

把 fuzz 输入解释为动作序列：

下面是状态机 target 的**多模块骨架**，依赖 `arbitrary`、`libfuzzer_sys`、被测状态机和独立参考模型。实现后运行对应 `cargo fuzz run`，并把 `256` 等资源上限纳入 target 契约与回归测试。

```rust,ignore
#[derive(Arbitrary, Debug)]
enum Action {
    Submit { qty: u16, price: u32 },
    Ack { id: u8 },
    Fill { id: u8, qty: u16 },
    Cancel { id: u8 },
    Disconnect,
    Reconnect,
}

fuzz_target!(|actions: Vec<Action>| {
    let mut sut = TradingState::new();
    let mut model = ReferenceModel::new();

    for action in actions.into_iter().take(256) {
        sut.apply(&action);
        model.apply(&action);
        assert_eq!(sut.observable_state(), model.observable_state());
        assert!(sut.invariants_hold());
    }
});
```

限制动作数可以防止单个样本执行过久。对于非法迁移，可以规定“返回明确错误且状态不变”，而不是强迫随机生成器只产生合法序列。

## 8. Sanitizer：让隐藏内存错误可见

纯 Safe Rust 能排除大量内存错误，但 HFT 项目常包含 FFI、`unsafe` ring buffer、mmap、SIMD 或 DPDK bindings。Fuzz 时应启用 sanitizer：

```bash
cargo fuzz run parse_market_packet --sanitizer address
cargo fuzz run parse_market_packet --sanitizer undefined
```

常见选择：

- AddressSanitizer：越界、use-after-free 等内存错误。
- UndefinedBehaviorSanitizer：部分未定义行为。
- MemorySanitizer：读取未初始化内存，环境要求更严格。
- ThreadSanitizer：数据竞争；通常与专门的并发测试分开运行。

Sanitizer 支持与 target、nightly 工具链和原生依赖有关。CI 应固定经过验证的工具链版本，并记录命令，而不是假定所有平台组合都可用。

此外，`cargo miri test` 能解释执行部分 unsafe Rust，发现违反 Rust 内存模型的行为。Miri 很慢，适合小而关键的 unsafe 单元，不适合替代长时间 fuzz。

## 9. 发现崩溃后的正确流程

Fuzzer 输出 crash artifact 只是开始：

1. 用完全相同的二进制、工具链和 artifact 重现。
2. 最小化输入，确认触发条件。
3. 判断是 panic、超时、OOM、UB 还是业务不变量破坏。
4. 修复根因，而不是在 target 中过滤该输入。
5. 把最小输入加入回归 corpus 或普通单元测试。
6. 检查相邻解析器、协议版本和相同 unsafe 模式。

```bash
cargo fuzz run parse_market_packet path/to/crash-artifact
cargo fuzz tmin parse_market_packet path/to/crash-artifact
```

命令细节可能随 `cargo-fuzz` 版本变化，CI 应固定版本，并以 `cargo fuzz --help` 的当前输出为准。

如果 artifact 含敏感行情或订单内容，应在上传 CI artifact、issue 或聊天系统前脱敏和访问控制。

## 10. 持续 Fuzz 的工程化

### 10.1 分层运行

| 位置 | 建议运行方式 |
| :--- | :--- |
| 每次提交 | 属性测试 + 已知 crash corpus，秒到分钟级 |
| Pull Request | 每个关键 target 短时 fuzz，发现明显回归 |
| Nightly | 多 target 并行，运行数十分钟到数小时 |
| 专用任务 | 长期持续 fuzz，语料去重并监控覆盖 |

### 10.2 关键指标

- 执行次数/秒：target 是否太重。
- corpus 数量与大小：是否持续发现新路径。
- 覆盖增长：训练是否停滞。
- 唯一 crash 数：先去重再告警。
- timeout/OOM：可能是资源放大，也可能是测试环境过小。

覆盖率是导航工具，不是安全证明。一个分支执行过，不代表所有状态和边界都正确。

### 10.3 语料治理

- 定期合并和最小化 corpus，减少重复执行。
- 所有 crash 都关联修复提交和回归测试。
- 协议升级时保留旧版本语料，除非明确停止支持。
- 固定 fuzz 工具链和依赖版本，让历史 artifact 可重现。

## 11. 常见误区

### 误区 1：没有 panic 就是正确

一个解析器可以安全地把买单解析成卖单而不 panic。必须在成功路径检查语义、不变量或参考实现。

### 误区 2：只 fuzz `&[u8]`

任意字节适合表层解析器，却可能永远到不了订单状态机。增加结构化消息和动作序列 target。

### 误区 3：失败就加 `if` 跳过

过滤 crash 输入会隐藏 bug。只有输入确实超出接口契约，且生产入口在调用前保证该契约时，才可收紧 fuzz 前置条件；最好把契约编码进类型。

### 误区 4：Fuzz target 调用真实网络和墙上时间

这会让执行慢、不可重现。把核心解析和状态转换提取成内存中的确定性函数，网络适配器另做集成测试。

### 误区 5：把无限随机等同于形式证明

Fuzz 是启发式搜索，不能穷尽 2^N 输入。关键并发算法还需要模型检查、代码审查和清晰的内存序证明。

## 12. 面试高频问答

### Q1：你会优先 fuzz HFT 系统的哪里？

优先选择攻击面大且损失半径高的边界：行情/订单协议解析器、编解码器、订单状态机、恢复逻辑和含 unsafe/FFI 的内存结构。原始字节 target 检查安全拒绝，结构化 target 检查业务不变量，动作序列 target 检查状态迁移。

### Q2：属性测试和 fuzz 有什么区别？

属性测试按人为定义的生成策略采样，并擅长 shrink；覆盖反馈 fuzz 会保留能探索新代码路径的变异输入。两者都需要清晰 oracle：固定预期、参考实现、守恒关系或状态不变量。

### Q3：如何测试解析器不仅“不崩”，而且“解析对”？

使用 round-trip、与独立参考解析器差分、golden fixture，以及长度、数量、校验和等协议不变量。对成功解析施加更强断言，对失败要求结构化错误且不修改状态。

### Q4：发现 fuzz crash 后怎么处理？

固定工具链重现并最小化，区分安全、资源和业务错误，修复根因，把最小输入升级为永久回归测试，再审计相似代码。不能只把输入加入黑名单。

## 13. 最终检查清单

- [ ] 每个高风险模块至少有一条清晰、可证伪的属性。
- [ ] 解析器同时有任意字节、合法结构化消息和真实脱敏 corpus。
- [ ] 成功路径检查语义，失败路径不 panic、不越界、不无限分配。
- [ ] 订单簿/状态机使用动作序列并与简单模型或守恒关系比较。
- [ ] unsafe、FFI、mmap 与 ring buffer 在可用平台上配合 sanitizer/Miri。
- [ ] fuzz target 确定、快速、无真实网络与 sleep，并限制输入和动作数量。
- [ ] crash 可重现、可最小化，修复后进入永久回归集合。
- [ ] CI 固定工具版本，分为提交级短跑与 nightly 长跑。
- [ ] corpus 和 artifact 不泄露交易、账户或协议敏感数据。

最有效的 fuzz 不是“让机器随机跑很久”，而是把最重要的交易规则写成机器能反驳的命题，然后持续给它机会找到反例。
