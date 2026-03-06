# C++ 向 Rust 迁移指南：实战与陷阱 (Migration Guide)

在 HFT 领域，绝大多数现存系统都是用 C++ 编写的。将系统迁移到 Rust 不是一蹴而就的，而是一个渐进的过程。本章将详细介绍如何安全、高效地进行 C++ 到 Rust 的重构，以及在混合编程中可能遇到的“雷区”。

## 1. 迁移策略：绞杀植物模式 (Strangler Fig Pattern)

不要试图一次性重写整个交易系统（Big Bang Rewrite）。这在工程上几乎注定失败。

**推荐路线**：
1.  **外围组件**: 从非关键路径开始，如风控网关 (Risk Gateway)、行情解析 (Market Data Decoder)、日志系统。
2.  **核心库**: 将通用的算法（如期权定价、无锁队列）提取为 Rust 库，供 C++ 调用。
3.  **核心逻辑**: 最后替换策略执行引擎 (Strategy Engine)。

### 1.1 混合构建架构 (Hybrid Build System)
通常有两种构建方式，取决于你的主导语言：

#### 方案 A: Rust 主导 (Greenfield / Small C++ Libs)
适合新项目引入遗留的 C++ 库。
*   **入口**: `cargo build`
*   **机制**: 使用 `build.rs` + `cc` crate 编译 C++ 代码并静态链接。
*   **优势**: 享受 Cargo 的依赖管理和测试工具。

```rust
// build.rs
fn main() {
    cxx_build::bridge("src/lib.rs")
        .file("src/cpp/legacy_pricing.cpp")
        .flag_if_supported("-std=c++17")
        .compile("cxx-bridge");

    println!("cargo:rerun-if-changed=src/lib.rs");
    println!("cargo:rerun-if-changed=src/cpp/legacy_pricing.cpp");
    println!("cargo:rerun-if-changed=src/cpp/legacy_pricing.h");
}
```

#### 方案 B: C++ 主导 (Brownfield / Large Legacy System)
适合现有大型 C++ 项目逐步引入 Rust 模块。
*   **入口**: `cmake`
*   **机制**: 使用 [Corrosion](https://github.com/corrosion-rs/corrosion) 在 CMake 中直接调用 Cargo。
*   **优势**: 无缝集成到现有的 CI/CD 流程中。

```cmake
# CMakeLists.txt
find_package(Corrosion REQUIRED)

corrosion_import_crate(MANIFEST_PATH rust_lib/Cargo.toml)

add_executable(hft_system main.cpp)
target_link_libraries(hft_system PUBLIC rust_lib)
```

## 2. 交互工具选择：为什么 HFT 必须用 `cxx`？

| 工具 | 适用场景 | 优点 | 缺点 |
| :--- | :--- | :--- | :--- |
| **[bindgen](https://github.com/rust-lang/rust-bindgen)** | 调用纯 C 接口 / 简单的 C++ 类 | 自动生成，省事 | 生成的代码全是 `unsafe`；对复杂的 C++ 模板/继承支持有限。 |
| **[cxx](https://github.com/dtolnay/cxx)** | **HFT 推荐**。双向调用 (Rust <-> C++) | **安全**！自动处理 `std::string` <-> `String`, `std::vector` <-> `Vec` 转换；生成的接口是 safe 的。 | 需要手写 schema 定义；不支持所有 C++ 特性（如复杂的模板元编程）。 |
| **[autocxx](https://github.com/google/autocxx)** | 高度自动化的 `cxx` | 尝试自动生成 `cxx` 绑定 | 还在实验阶段，不如 `cxx` 稳定。 |

**HFT 场景强烈推荐使用 `cxx`**。它不仅仅是一个 FFI 库，更是一个**边界安全检查器**。它在编译期就能捕获大部分所有权混淆问题。

## 3. 实战：数据类型映射与传递

### 3.1 字符串与向量 (Strings & Vectors)
`cxx` 会自动处理内存布局转换。

```rust
// src/lib.rs
#[cxx::bridge]
mod ffi {
    extern "Rust" {
        fn process_market_data(symbols: &Vec<String>, prices: &Vec<f64>) -> Result<()>;
    }
}

fn process_market_data(symbols: &Vec<String>, prices: &Vec<f64>) -> Result<(), anyhow::Error> {
    for (sym, price) in symbols.iter().zip(prices) {
        // Rust String 自动转为 C++ string view (zero-copy)
        println!("Symbol: {}, Price: {}", sym, price);
    }
    Ok(())
}
```

### 3.2 复杂结构体 (Structs)
在 FFI 边界定义共享结构体。

```rust
#[cxx::bridge]
mod ffi {
    struct Order {
        id: u64,
        price: u64,
        qty: u32,
        side: u8, // 0=Buy, 1=Sell
    }

    extern "C++" {
        include!("hft/order_manager.h");
        type OrderManager;
        
        // 传递结构体 By Value
        fn submit_order(self: Pin<&mut OrderManager>, order: Order);
    }
}
```

### 3.3 智能指针与所有权 (Smart Pointers)
这是最容易出错的地方。
*   `UniquePtr<T>` -> `std::unique_ptr<T>`: 独占所有权。
*   `SharedPtr<T>` -> `std::shared_ptr<T>`: 共享所有权。
*   `Box<T>` -> Rust 堆对象传给 C++ 管理。

**规则**: 谁创建，谁负责。尽量不要在 C++ 中 `delete` Rust 创建的对象，反之亦然。使用智能指针自动管理生命周期。

## 4. 技术挑战与“深水区” (The Deep Water)

迁移不仅是语言的转换，更是思维模式的冲突。以下是我们在实际迁移中遇到的最大技术障碍。

### 4.1 模板元编程 (Template Metaprogramming)
HFT 的 C++ 代码通常大量使用模板来实现编译期多态（CRTP, SFINAE, Concepts），以消除虚函数开销。
*   **挑战**: `bindgen` 和 `cxx` **完全不支持** C++ 模板。你无法直接调用 `OrderBook<NYSE>`。
*   **解决**:
    *   **手动特化 (Manual Monomorphization)**: 在 C++ 侧写辅助函数，实例化特定类型的模板，导出为普通函数。
        ```cpp
        // C++ Side
        using NYSEBook = OrderBook<NYSE>;
        void process_nyse(NYSEBook& book, const Order& o) { book.add(o); }
        ```
    *   **Rust 泛型重写**: 如果逻辑不复杂，直接用 Rust 的 Generic + Trait 重写。Rust 的 Trait 系统比 C++ 模板更结构化，但表达能力略有不同（例如没有非类型模板参数的偏特化，直到 const generics 稳定）。

### 4.2 继承与虚函数 (Inheritance & Virtual Functions)
*   **挑战**: Rust 没有继承。如果 C++ 代码严重依赖类层次结构（如 `BaseStrategy -> MomentumStrategy`），很难直接映射。
*   **解决**:
    *   **组合优于继承**: 将基类逻辑提取为 `struct BaseContext`，作为成员包含在 Rust 结构体中。
    *   **Trait Object**: 将 C++ 的虚基类映射为 Rust 的 `dyn Trait`。`cxx` 支持调用 C++ 的虚函数，但需要小心生命周期。

### 4.3 异常安全 (Exception Safety)
这是最容易导致 **Undefined Behavior (UB)** 的地方。
*   **问题**: C++ 抛出异常跨越 FFI 边界进入 Rust，或者 Rust panic 跨越边界进入 C++，都会导致程序立即崩溃（abort）或堆栈损坏。
*   **解决**:
    *   **C++ -> Rust**: `cxx` 会自动捕获 C++ 异常并转换为 Rust `Result`。**不要**在 `extern "C"` 中直接抛出异常。
    *   **Rust -> C++**: 在 `Cargo.toml` 中设置 `panic = "abort"`。这是 HFT 的标准做法。在低延迟系统中，Panic 意味着不可恢复的错误，直接 crash 比数据损坏更安全。

```toml
[profile.release]
panic = "abort"
```

### 4.4 编译与链接复杂性
*   **挑战**: 两个编译器（rustc, clang++）、两个构建系统（Cargo, CMake）、两个标准库（libc++, libstd）。符号冲突、ABI 不兼容、链接顺序错误是家常便饭。
*   **解决**: 统一工具链。强制要求 C++ 项目使用 `clang` 编译，并确保其版本与 Rust 使用的 LLVM 版本一致。使用 `cxx` 提供的 `build.rs` 辅助脚本来自动处理链接参数。

### 4.5 性能陷阱：跨语言内联 (Cross-Language LTO)
默认情况下，C++ 编译器看不到 Rust 的函数体，Rust 也看不到 C++ 的。这意味着像 `get_price()` 这种极小的函数无法被内联，每次调用都有函数调用开销（约 2-5ns）。

**解决方案**: 开启 LTO。
1.  **版本匹配 (Version Matching)**: 这是一个大坑。Rustc 确实绑定了一个特定版本的 LLVM。你必须找出你当前 Rustc 使用的 LLVM 版本，然后强制 C++ 使用**完全相同主版本**的 `clang`。
    *   查看 Rust LLVM 版本: `rustc --version --verbose` (例如 `LLVM 16.0.4`)。
    *   那么你编译 C++ 必须用 `clang-16`。如果用 `clang-14` 或 `clang-17`，LTO 链接时会直接报错或产生错误的机器码。
2.  **Rust 端**: `lto = true`, `linker_plugin_lto = true`.
3.  **C++ 端**: 使用 `clang++` 并开启 `-flto`.

### 4.3 内存对齐 (Alignment)
Rust 的 `#[repr(Rust)]` 内存布局是不确定的。
**必须**使用 `#[repr(C)]` 标记所有跨语言共享的结构体，并确保双方对齐一致。

```rust
#[repr(C, align(64))] // 强制 Cache Line 对齐
pub struct AtomicCounter {
    pub value: std::sync::atomic::AtomicU64,
}
```

## 5. 进阶技巧与最佳实践 (Advanced Techniques)

### 5.1 不透明句柄模式 (Opaque Handle Pattern)
当 C++ 和 Rust 需要共享一个对象（如 `std::shared_ptr<Context>`），但又不想暴露其内部布局时，使用此模式。

**C++ 侧 (`context_wrapper.h`)**:
```cpp
#pragma once
#include <memory>
#include "legacy_context.h"

// 包装类，持有 shared_ptr
struct ContextHandle {
    std::shared_ptr<LegacyContext> ptr;
    explicit ContextHandle(std::shared_ptr<LegacyContext> p) : ptr(p) {}
};

// 导出的工厂函数
std::unique_ptr<ContextHandle> create_context();
void use_context(const ContextHandle& handle);
```

**Rust 侧 (`lib.rs`)**:
```rust
#[cxx::bridge]
mod ffi {
    unsafe extern "C++" {
        include!("context_wrapper.h");
        type ContextHandle;

        fn create_context() -> UniquePtr<ContextHandle>;
        fn use_context(handle: &ContextHandle);
    }
}

pub struct RustContext {
    // Rust 并不持有 shared_ptr 本身，而是持有其 Wrapper 的 UniquePtr
    // 这样避免了跨语言引用计数的原子操作同步问题
    handle: cxx::UniquePtr<ffi::ContextHandle>,
}
```

### 5.2 跨语言 LTO 配置详解
为了消除 FFI 开销，必须让 Linker 能“看穿”边界。

1.  **编译器版本一致**: 确保 `clang++` 和 `rustc` 使用相同的 LLVM 后端版本 (如 LLVM 16)。
2.  **Rust 配置 (`Cargo.toml`)**:
    ```toml
    [profile.release]
    lto = true # 或 "thin"
    codegen-units = 1
    ```
3.  **C++ 配置 (`CMakeLists.txt`)**:
    ```cmake
    # 使用 Clang 并开启 ThinLTO
    set(CMAKE_CXX_COMPILER "clang++")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -flto=thin")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -fuse-ld=lld -Wl,--plugin-opt=O3")
    ```

### 5.3 调试混合栈 (Debugging Mixed Stacks)
当程序崩溃时，你需要能看到跨语言的调用栈。
*   **工具**: 使用 `lldb` (macOS) 或 `gdb` (Linux)。Rust 自带的 `rust-lldb` / `rust-gdb` 包装器对 Rust 符号支持更好。
*   **技巧**: 编译时保留符号表。
    *   Rust: `[profile.release] debug = true` (这不会影响运行时性能，只会增大二进制体积)。
    *   C++: `-g` (Release with Debug Info).
*   **ASan 集成**:
    在 Rust 中启用 ASan 需要 nightly toolchain：
    ```bash
    RUSTFLAGS="-Zsanitizer=address" cargo build --target x86_64-unknown-linux-gnu
    ```
    同时 C++ 也要用 `-fsanitize=address` 编译。

### 5.4 从继承到 Trait：思维重构 (Refactoring Mindset)

C++ 的继承通常承载了两件事：
1.  **代码复用**: 基类实现公共逻辑 (`Base::log()`)。
2.  **多态**: 虚函数覆盖 (`Derived::on_tick()`)。

在 Rust 中，这两者是分离的。

#### 案例：策略继承体系
**C++ 代码**:
```cpp
class Strategy {
protected:
    Context ctx;
public:
    void send_order(Order o) { ctx.send(o); } // 代码复用
    virtual void on_tick(Tick t) = 0;         // 多态接口
};

class Momentum : public Strategy {
    void on_tick(Tick t) override { ... }
};
```

**Rust 重构方案**:

1.  **提取公共状态 (Composition)**:
    不要继承 `Context`，而是包含它。
    ```rust
    struct StrategyContext {
        // ... socket, logs, etc
    }
    
    impl StrategyContext {
        fn send_order(&mut self, order: Order) { ... }
    }
    ```

2.  **定义行为接口 (Trait)**:
    ```rust
    trait Strategy {
        fn on_tick(&mut self, tick: &Tick, ctx: &mut StrategyContext);
    }
    ```

3.  **具体实现 (Implementation)**:
    ```rust
    struct MomentumStrategy {
        // 自己的状态
        window: Vec<f64>,
    }

    impl Strategy for MomentumStrategy {
        fn on_tick(&mut self, tick: &Tick, ctx: &mut StrategyContext) {
            // 使用 ctx 发单
            if self.calculate_signal(tick) {
                ctx.send_order(Order::new(...));
            }
        }
    }
    ```

4.  **静态分发 (Static Dispatch)**:
    在 HFT 中，我们极力避免 `Box<dyn Strategy>` (虚表调用)。我们使用泛型 `T: Strategy`。
    ```rust
    struct Engine<S: Strategy> {
        context: StrategyContext,
        strategy: S, // 编译期确定的具体类型，无虚函数开销
    }
    
    impl<S: Strategy> Engine<S> {
        fn run(&mut self) {
            while let Some(tick) = self.context.next_tick() {
                // 这一行会被内联优化，完全没有函数调用开销
                self.strategy.on_tick(&tick, &mut self.context);
            }
        }
    }
    ```

这种 **Trait + Generic** 的模式（即 Static Dispatch）是 Rust 性能超越 C++ 虚函数的关键。C++ 需要用 CRTP (Curiously Recurring Template Pattern) 这种极其晦涩的技巧才能达到的效果，在 Rust 里就是默认写法。

## 6. 常见面试题 (Q&A)

### Q1: 你们如何保证重构后的正确性？(Shadow Mode)
**问题背景**: HFT 系统容错率为零。你不能简单地上线一个新模块，然后祈祷它不出错。
**回答**:
"我们绝对不会直接替换。我们采用**影子模式 (Shadow Mode)** 策略：
1.  **并行运行**: 在生产环境中，C++ 旧模块和 Rust 新模块同时接收市场数据。
2.  **只读不写**: Rust 模块执行所有计算逻辑，但**禁止发单**。它的输出（如定价、信号）被写入专门的日志或 RingBuffer。
3.  **实时比对**: 有一个旁路脚本（或专门的 Verify 线程）实时消费 C++ 和 Rust 的输出。
    *   **一致性**: 检查价格、数量是否完全一致（Bit-wise identical）。
    *   **延迟**: 检查 Rust 的时间戳是否优于 C++。
4.  **灰度切换**: 只有当连续运行一周且 99.9999% 的结果一致时，我们才会通过配置开关，将发单权限切换给 Rust。"

### Q2: 跨语言调用的开销有多大？如何优化？
**问题背景**: 很多人认为 FFI 很慢，不适合高频。
**回答**:
"如果不开启 LTO，每次 FFI 调用大约有 **3-5ns** 的开销（主要是寄存器保存、栈调整、无法内联）。这在每秒千万级调用下是可观的。
我们有三个优化层次：
1.  **Chunky Interface (粗粒度接口)**: 不要让 C++ 循环调 Rust。比如不要 `for i in 0..100 { rust_process(i) }`，而是传一个 `Vec` 给 Rust，让 Rust 内部循环 `rust_process_batch(vec)`。这能分摊 FFI 开销。
2.  **Cross-Language LTO**: 我们确保 Rust 和 C++ 使用相同版本的 LLVM（如 LLVM 16），并开启 `linker_plugin_lto`。这允许编译器看穿 FFI 边界，实现跨语言内联，将开销降为 **0ns**。
3.  **Shared Memory**: 对于极度敏感的数据，我们直接在 C++ 分配一块内存（如 `std::vector`），通过指针传给 Rust。双方直接读写这块内存，完全绕过函数调用。"

### Q3: 如果 C++ 端发生了 Segfault，Rust 能救吗？
**问题背景**: Rust 标榜内存安全，但和 unsafe 的 C++ 混编时，这种保证还存在吗？
**回答**:
"**救不了**。Rust 的安全保证止步于 FFI 边界。如果 C++ 破坏了堆内存（Heap Corruption）或者访问了野指针，整个进程（包括 Rust 部分）都会崩溃。
为了缓解这个问题，我们采取防御性编程：
1.  **Sanitizers**: 在开发和 CI 阶段，必须开启 `AddressSanitizer (ASan)` 运行混合代码。这能捕获 90% 的内存越界。
2.  **隔离 (Isolation)**: 如果某个遗留 C++ 模块非常不稳定，我们会把它拆分成独立的进程，通过共享内存（SHM）或 IPC 通信。这样它崩了只会重启它自己，不会拖垮主策略进程。
3.  **Crash 优于 Corruption**: 我们配置 Rust `panic = 'abort'`。在 HFT 中，带着错误的数据继续运行比直接死掉更可怕（可能导致巨额亏损）。所以一旦检测到异常，立即自杀是最佳策略。"

### Q4: 怎么处理 C++ 的 `std::shared_ptr` 和 Rust 的 `Arc`？
**问题背景**: 两种语言都有引用计数，怎么互通？
**回答**:
"这是一个棘手的问题，因为它们的内存布局完全不同，原子操作的实现也不一定兼容。
通常做法是**不互通**，而是**持有句柄 (Opaque Handle)**：
*   **Rust 持有 C++**: Rust struct 中存放一个 `cxx::SharedPtr<CppClass>`。Rust 克隆时，调用 C++ 的拷贝构造函数增加引用计数。
*   **C++ 持有 Rust**: C++ 存放一个 `Box<Arc<RustStruct>>` 的裸指针。这需要手动管理引用计数（调用 Rust 导出的 `clone` 和 `drop` 函数），非常容易出错。
**最佳实践**: 尽量避免跨语言共享所有权。明确**单一所有权 (Single Ownership)**：要么是 C++ 拥有并在用完后通知 Rust，要么是 Rust 拥有并借用给 C++。如果必须共享，优先考虑使用对象池 (Object Pool) + ID 索引的方式，而不是传递指针。"
