# 订单路由系统 (Order Routing)

在高频交易系统中，订单路由（Order Routing）是将策略生成的交易指令（New Order, Cancel, Replace）快速、准确地发送到交易所的核心组件。与市场数据处理（Market Data）主要关注吞吐量和解码速度不同，订单路由系统对**端到端延迟（End-to-End Latency）**和**确定性（Determinism）**有着极高的要求。

本章将构建一个低延迟、零拷贝、无锁的订单路由系统。

## 1. 理论背景 (Theory & Context)

### 1.1 关键路径延迟 (Critical Path Latency)

在 HFT 中，"Tick-to-Trade" 延迟是指从接收到市场数据更新到发出订单网络包的时间。订单路由系统占据了其中相当大的一部分（策略计算通常非常快）。

典型的订单生命周期：
1.  策略决定买入。
2.  构建 `NewOrderSingle` 消息。
3.  **风控检查 (Pre-trade Risk Check)**。
4.  序列化为交易所协议格式 (FIX/SBE/OUCH)。
5.  写入网卡缓冲区 (Kernel Bypass/Socket Send)。

### 1.2 架构设计：Thread-per-Core

为了最小化延迟，我们通常采用 **Thread-per-Core** 模型，将策略逻辑和订单发送逻辑绑定在同一个核心，或者通过极其高效的 SPSC 队列连接策略核心与网络核心。

*   **Inline Sending (同核发送)**: 策略直接调用 socket send。延迟最低，但如果 socket 阻塞（TCP Window Full），会阻塞策略计算。
*   **Offload Sending (异核发送)**: 策略将订单写入 RingBuffer，由独立的网络线程发送。增加了队列延迟（约 50-200ns），但隔离了网络抖动。

本章将采用 **Offload Sending** 模式，因为通过 `io_uring` 或 DPDK 优化的队列延迟可以忽略不计，且系统稳定性更高。

## 2. 核心实现 (Implementation)

### 2.1 订单结构设计 (Order Structure)

为了避免内存分配，我们必须使用定长结构体（Fixed-size Struct）来表示订单，或者使用 `enum` 配合 `repr(C)`。

```rust
use crate::common::types::{Price, Quantity, Side, SymbolId, ClOrdId};

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct NewOrder {
    pub symbol_id: SymbolId,
    pub price: Price,
    pub quantity: Quantity,
    pub side: Side,
    pub cl_ord_id: ClOrdId, // Client Order ID, 必须唯一
    pub time_in_force: TimeInForce,
}

#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum TimeInForce {
    Day = 0,
    IOC = 1, // Immediate or Cancel
    FOK = 2, // Fill or Kill
    GTD = 3, // Good Till Date
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct CancelOrder {
    pub symbol_id: SymbolId,
    pub orig_cl_ord_id: ClOrdId, // 要取消的订单 ID
}

// 使用 enum 分发，避免 Box<dyn Order>
#[derive(Debug, Clone, Copy)]
pub enum OrderRequest {
    New(NewOrder),
    Cancel(CancelOrder),
    Replace(ReplaceOrder), // 修改订单
}
```

### 2.2 客户端订单 ID (ClOrdID) 生成

生成唯一的 ClOrdID 是一个常见的性能瓶颈。使用 `UUID` 是绝对禁止的（太慢且太长）。通常我们使用 `u64`，由以下部分组成：
*   **Strategy ID** (8 bits): 区分不同策略。
*   **Thread ID** (8 bits): 区分不同线程。
*   **Sequence** (48 bits): 递增序列号。

```rust
use std::sync::atomic::{AtomicU64, Ordering};

pub struct IdGenerator {
    prefix: u64,
    seq: AtomicU64,
}

impl IdGenerator {
    pub fn new(strategy_id: u8, thread_id: u8) -> Self {
        // High 16 bits: Strategy ID | Thread ID
        let prefix = ((strategy_id as u64) << 56) | ((thread_id as u64) << 48);
        Self {
            prefix,
            seq: AtomicU64::new(1),
        }
    }

    #[inline(always)]
    pub fn next(&self) -> u64 {
        // fetch_add 在 x86 上是 LOCK XADD，约 5-10ns
        // 如果是单线程使用，可以使用 Cell<u64> 降至 <1ns
        self.prefix | self.seq.fetch_add(1, Ordering::Relaxed)
    }
}
```

### 2.3 订单网关 (Order Gateway)

网关负责接收 `OrderRequest`，进行序列化，并发送到网络。

```rust
use ringbuf::{Producer, Consumer, RingBuffer};

pub struct OrderGateway {
    // 接收来自策略的指令
    rx: Consumer<OrderRequest>,
    // 发送执行报告给策略
    tx: Producer<ExecutionReport>,
    // 网络连接 (模拟)
    stream: TcpStream, 
    // 序列化缓冲区
    buffer: Vec<u8>,
}

impl OrderGateway {
    pub fn new(rx: Consumer<OrderRequest>, tx: Producer<ExecutionReport>) -> Self {
        Self {
            rx,
            tx,
            stream: TcpStream::connect("127.0.0.1:8080").unwrap(), // 实际应为非阻塞
            buffer: Vec::with_capacity(4096),
        }
    }

    pub fn poll(&mut self) {
        // 1. 处理发出的订单
        while let Some(req) = self.rx.pop() {
            self.process_request(req);
        }

        // 2. 处理收到的回报 (Execution Reports)
        // self.read_from_socket();
    }

    #[inline]
    fn process_request(&mut self, req: OrderRequest) {
        self.buffer.clear();
        
        // 序列化 (以 OUCH 协议为例)
        match req {
            OrderRequest::New(o) => self.encode_new_order(o),
            OrderRequest::Cancel(c) => self.encode_cancel_order(c),
            _ => {},
        }

        // 写入 Socket
        // 在生产环境中，这里应当处理 EAGAIN/EWOULDBLOCK
        // 并且可能需要批量发送 (Batching)
        self.stream.write_all(&self.buffer).ok();
    }

    fn encode_new_order(&mut self, o: NewOrder) {
        // OUCH Enter Order Message
        self.buffer.push(b'O'); // Type
        self.buffer.extend_from_slice(&o.cl_ord_id.to_le_bytes());
        self.buffer.extend_from_slice(&o.symbol_id.to_le_bytes());
        self.buffer.push(if o.side == Side::Buy { b'B' } else { b'S' });
        self.buffer.extend_from_slice(&o.quantity.to_le_bytes());
        self.buffer.extend_from_slice(&o.price.to_le_bytes());
        // ... 其他字段
    }
}
```

### 2.4 零拷贝序列化 (Zero-Copy Serialization)

上面的 `encode_new_order` 使用了 `Vec::push`，虽然有预分配，但仍然涉及内存拷贝。极致优化可以使用 `struct` 内存布局直接映射（如果字节序和对齐允许），或者使用 `bytes::BufMut`。

更激进的做法是直接在栈上构建数据包，然后传递切片：

```rust
// SAFETY: 结构体必须是 #[repr(C, packed)] 或严格控制对齐
#[repr(C, packed)]
struct OuchEnterOrder {
    msg_type: u8,
    cl_ord_id: u64,
    token: u32,
    side: u8,
    quantity: u32,
    price: u64,
    // ...
}

fn send_fast(stream: &mut TcpStream, order: &NewOrder) {
    let packet = OuchEnterOrder {
        msg_type: b'O',
        cl_ord_id: order.cl_ord_id.to_le(), // 确保字节序
        token: 0,
        side: if order.side == Side::Buy { b'B' } else { b'S' },
        quantity: order.quantity.to_le(),
        price: order.price.to_le(),
    };

    // 将结构体视为字节切片
    let bytes = unsafe {
        std::slice::from_raw_parts(
            &packet as *const _ as *const u8,
            std::mem::size_of::<OuchEnterOrder>()
        )
    };
    
    stream.write_all(bytes).ok();
}
```

> **注意**: `packed` 结构体可能会导致未对齐访问，在某些 CPU 架构（如 ARM）上会触发异常或严重性能下降。在 x86_64 上通常没问题，但要注意字段访问方式。

## 3. 性能分析 (Performance Analysis)

### 3.1 内存对齐与填充 (Padding)

Rust 的 `enum` 大小由最大的变体决定 + tag 大小。如果 `OrderRequest` 中 `NewOrder` 很大（例如 100 字节），而 `CancelOrder` 很小（16 字节），那么传递 `OrderRequest` 会浪费带宽和缓存。

**优化方案**:
1.  **拆分队列**: 为 `NewOrder` 和 `CancelOrder` 使用不同的 SPSC 队列。
2.  **SoA (Structure of Arrays)**: 极其复杂，通常不用于订单流。
3.  **Union**: 使用 `untagged union` (unsafe) 只有在极致优化时考虑。

### 3.2 缓存行伪共享 (False Sharing)

订单 ID 生成器 `IdGenerator` 如果被多个线程共享，`seq: AtomicU64` 会成为热点，导致严重的 Cache bouncing。

**解决方案**:
每个线程/策略实例拥有独立的 `IdGenerator`，且确保其独占 Cache Line（使用 `#[repr(align(64))]`）。

```rust
#[repr(align(64))]
pub struct AlignedIdGenerator {
    // ...
}
```

## 4. 常见陷阱 (Pitfalls)

### 4.1 幻影订单 (Phantom Orders)

如果网关发送了订单，但在收到交易所确认（Ack）之前崩溃或重启，策略恢复后不知道该订单的状态。

**对策**:
*   **持久化**: 在发送前将 Sequence Number 写入共享内存或极低延迟的日志文件（如 NVMe namespace）。
*   **Reconcile**: 重启连接时，使用交易所的 `MassStatusRequest` 查询所有活跃订单。

### 4.2 序列号回绕 (Sequence Number Rollover)

FIX 协议通常要求 SeqNum 每天重置。但如果内部 ClOrdID 使用 u32 且交易量极大，可能会在盘中溢出。

**对策**:
*   始终使用 `u64` 作为内部 ID。
*   在协议层进行映射（如果协议只支持 u32 字符串，如某些旧版 FIX）。

### 4.3 错误的 TCP 拥塞控制

默认的 TCP 开启了 Nagle 算法（合并小包）。对于 HFT，必须禁用。

```rust
stream.set_nodelay(true).expect("Failed to set TCP_NODELAY");
```

此外，如果交易所接收窗口为 0，`write` 调用可能会阻塞。非阻塞模式下会返回 `WouldBlock`。

**处理 Backpressure**:
如果 Socket 缓冲区满，网关线程应该：
1.  停止从策略队列读取新订单（产生背压）。
2.  缓冲当前消息（如果必须）。
3.  **绝对不能** 丢弃订单。

## 5. 延伸阅读

*   **SBE (Simple Binary Encoding)**: 高性能二进制编码标准。
*   **Disruptor Pattern**: LMAX 交易所的高性能队列模型。
