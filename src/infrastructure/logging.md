# 高性能日志 (Logging)

在 HFT 系统中，日志是唯一不能丢、但又最容易成为瓶颈的组件。一条简单的 `println!` 或 `log::info!` 可能会导致几十微秒的延迟，这在交易路径上是不可接受的。

本章将教你如何设计一个**纳秒级、零分配、异步**的日志系统。

## 1. 理论背景：日志的开销

### 1.1 为什么标准日志慢？
1.  **I/O 阻塞**: `stdout` 或文件写入是系统调用 (Syscall)，涉及上下文切换。
2.  **格式化开销**: `format!("Price: {:.2}", price)` 需要在运行时解析格式字符串，并将浮点数转为字符串。
3.  **内存分配**: 拼接字符串通常涉及 `String` 的 `malloc`。
4.  **锁**: `println!` 内部有锁，多线程并发时会竞争。

### 1.2 理想的 HFT 日志
- **异步 (Async)**: 交易线程只负责把数据扔进队列，后台线程负责写盘。
- **二进制 (Binary)**: 交易线程不进行字符串格式化，只记录原始数据 (struct)。格式化留给后台线程或离线工具。
- **零分配 (Zero-Allocation)**: 消息对象在 Ring Buffer 中复用。

## 2. 核心架构

我们将构建一个基于 Ring Buffer 的异步日志系统。

```mermaid
graph LR
    T[交易线程] -->|1. Push Event| RB[Ring Buffer]
    RB -->|2. Pop Event| L[日志线程]
    L -->|3. Format & Write| F[文件/IO]
```

### 2.1 日志事件定义

为了避免分配，我们使用 `enum` 来承载不同类型的日志，或者使用 `union`。

```rust
#[derive(Clone, Copy)]
pub enum LogEvent {
    OrderPlaced { id: u64, price: f64, size: u32 },
    OrderFilled { id: u64, price: f64 },
    Error { code: u16 },
    // 预留填充，确保 Cache Line 对齐
    _Padding([u8; 40]), 
}

// 确保 Event 大小固定且拷贝开销小
static_assertions::const_assert!(std::mem::size_of::<LogEvent>() <= 64);
```

### 2.2 极简 Logger 实现

利用我们之前写的 `MpscArrayQueue` 或 `SPSC` (如果是单线程策略)。

```rust
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::fs::File;
use std::io::Write;

pub struct AsyncLogger {
    queue: MpscArrayQueue<LogEvent>, // 假设这是我们在前面章节实现的
    running: AtomicBool,
}

impl AsyncLogger {
    pub fn new(file_path: &str) -> (Self, thread::JoinHandle<()>) {
        let queue = MpscArrayQueue::new(1024 * 1024); // 1M 容量
        let logger = Self {
            queue,
            running: AtomicBool::new(true),
        };
        
        let mut file = File::create(file_path).unwrap();
        
        // 启动后台线程
        let handle = thread::spawn(move || {
            // 将线程绑定到特定的 Core (例如 Core 3)
            core_affinity::set_for_current(core_affinity::CoreId { id: 3 });
            
            while logger.running.load(Ordering::Relaxed) {
                while let Some(event) = logger.queue.pop() {
                    // 3. 延迟格式化 (Delayed Formatting)
                    match event {
                        LogEvent::OrderPlaced { id, price, size } => {
                            writeln!(file, "PLACED,{},{:.2},{}", id, price, size).ok();
                        }
                        LogEvent::OrderFilled { id, price } => {
                            writeln!(file, "FILLED,{},{:.2}", id, price).ok();
                        }
                        _ => {}
                    }
                }
                // 空闲时自旋或 Yield
                std::hint::spin_loop();
            }
        });

        (logger, handle)
    }

    // 热路径上的 API: 极快，无锁，无分配
    pub fn log(&self, event: LogEvent) {
        if let Err(_) = self.queue.push(event) {
            // 队列满了！策略：
            // 1. 丢弃 (Drop) - 保证低延迟
            // 2. 阻塞 (Block) - 保证数据完整
            // HFT 通常选 1，并记录一个 "Dropped" 计数器
            eprintln!("Log queue full!"); 
        }
    }
}
```

## 3. 进阶优化

### 3.1 时间戳 (Timestamping)
不要在热路径调用 `SystemTime::now()`，它是系统调用，慢。
**优化**: 使用 CPU 的 TSC (Time Stamp Counter) 寄存器。

```rust
pub fn rdtsc() -> u64 {
    unsafe { std::arch::x86_64::_rdtsc() }
}
```
在日志线程中，再将 TSC 转换为真实时间（通过定期校准）。

### 3.2 结构化二进制日志 (SBE - Simple Binary Encoding)
与其在后台线程 `writeln!` 文本，不如直接把 `LogEvent` 的内存 `memcpy` 到内存映射文件 (mmap) 中。
这能达到磁盘 IO 的物理极限。
离线时，再写一个解析器把二进制转为 CSV/JSON。

### 3.3 避免 False Sharing
日志队列的 `head` 和 `tail` 同样需要 Padding。
交易线程只写 `tail`，日志线程只读 `tail`。

## 4. 常见陷阱 (Pitfalls)

1.  **队列溢出**:
    当磁盘 I/O 抖动（例如 SSD GC）时，日志线程会变慢，导致队列瞬间填满。
    **解决**: 
    - 增大队列容量 (例如 1GB)。
    - 使用 `O_DIRECT` 绕过 Page Cache。
    - 关键日志阻塞，非关键日志丢弃。

2.  **字符串处理**:
    如果必须记录动态字符串（如错误信息），不要用 `String`。
    **解决**: 使用定长数组 `[u8; 64]` 或索引到静态字符串表 `&'static str`。

## 5. 延伸阅读

- [Nanolog](https://github.com/PlatformLab/NanoLog) - C++ 极速日志库，宣称比 `printf` 快 100 倍。
- [SftLog](https://github.com/SftLogic/sft_log) - Rust 实现的无锁日志。

---
下一章：[配置热加载 (Configuration)](config.md)
