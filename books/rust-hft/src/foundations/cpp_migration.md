# C++ 向 Rust 迁移：策略与陷阱 (Migration Guide)

许多数据库、推理运行时、网络服务和交易系统长期建立在 C++ 之上。将其中一部分迁移到 Rust，不只是翻译语法，还会改变所有权、错误传播、构建和应用二进制接口（Application Binary Interface，ABI）。可验证的迁移需要明确组件边界、双向类型契约和回滚方式。

## 1. 迁移策略：绞杀植物模式 (Strangler Fig Pattern)

一次性重写整个交易系统（Big Bang Rewrite）会同时放大语义差异、验证范围和回滚风险。除非系统很小且已有完整的可重复验收环境，更稳妥的起点通常是可独立替换、可影子运行的边界。

常见拆分方式如下：
1.  **可隔离组件**: 优先选择有清晰输入输出、可回放且能快速回滚的模块，例如日志、报表或旁路校验；行情解析等数据面组件只有在具备完整回放与影子验证时才适合作为早期目标。
2.  **核心库**: 将通用的算法（如期权定价、无锁队列）提取为 Rust 库，供 C++ 调用。
3.  **核心逻辑**: 最后替换策略执行引擎 (Strategy Engine)。

### 1.1 混合构建架构 (Hybrid Build System)
通常有两种构建方式，取决于你的主导语言：

#### 方案 A: Rust 主导 (Greenfield / Small C++ Libs)
适合新项目引入遗留的 C++ 库。
*   **入口**: `cargo build`
*   **机制**: 使用 `build.rs` + `cc` crate 编译 C++ 代码并静态链接。
*   **优势**: 享受 Cargo 的依赖管理和测试工具。

下面是多文件构建脚本，需要 `cxx-build` 构建依赖和对应的 C++ 源码/头文件；mdBook 的单文件测试无法构造这套工程，因此不执行该片段。

```rust,ignore
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

## 2. 交互工具选择：何时使用 `cxx`？

| 工具 | 适用场景 | 优点 | 缺点 |
| :--- | :--- | :--- | :--- |
| **[bindgen](https://github.com/rust-lang/rust-bindgen)** | 调用 C 接口或可由 Clang 解析的部分 C++ 头文件 | 自动生成底层声明，减少手抄 ABI | 主要提供低层 FFI，仍需自行封装和审计 unsafe 边界；复杂模板/继承难以直接形成自然 Rust API。 |
| **[cxx](https://github.com/dtolnay/cxx)** | 受支持类型范围内的双向 Rust/C++ 调用 | 用 bridge schema 显式描述边界，并为受支持签名生成较安全的封装 | 需要手写 schema；不能直接表达任意 C++ API，边界外的 C++ 安全性仍需调用者保证。 |
| **[autocxx](https://github.com/google/autocxx)** | 希望从 C++ 头文件生成较高层绑定 | 在 `cxx` 等组件之上减少部分手工桥接 | 支持范围与生成结果随版本变化，采用前应针对真实头文件做原型验证。 |

`cxx` 常适合希望显式收窄接口、且类型落在其支持范围内的项目；已有稳定 C ABI 时，手写 C façade + `bindgen` 可能更简单。选择标准应是：能否表达现有 API、生成代码能否审计、所有权是否清晰、构建链是否可复现，而不是工具名称本身。

## 3. 实战：数据类型映射与传递

### 3.1 字符串与向量 (Strings & Vectors)
`cxx` 会为受支持的桥接类型生成两侧胶水代码。某个参数是借用、移动还是发生转换，应以该签名和生成代码为准，不能笼统假设“全部零拷贝”。

下面代码依赖 `cxx` 宏、`anyhow` 和生成的跨语言胶水，只有放进完整 Cargo/C++ 工程才有意义，因此 mdBook 不执行它。

```rust,ignore
// src/lib.rs
#[cxx::bridge]
mod ffi {
    extern "Rust" {
        fn process_market_data(symbols: &Vec<String>, prices: &Vec<f64>) -> Result<()>;
    }
}

fn process_market_data(symbols: &Vec<String>, prices: &Vec<f64>) -> Result<(), anyhow::Error> {
    for (sym, price) in symbols.iter().zip(prices) {
        // 这里只在 Rust 侧按引用读取；跨边界的具体表示由 bridge 签名决定。
        println!("Symbol: {}, Price: {}", sym, price);
    }
    Ok(())
}
```

### 3.2 复杂结构体 (Structs)
在 FFI 边界定义共享结构体。

该 bridge 还依赖 `cxx`、C++ 头文件和其中定义的 `OrderManager`；这是多文件 FFI 接口定义，不是标准库独立示例，mdBook 不执行它。

```rust,ignore
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
*   `Box<T>` -> Rust 拥有的堆对象可以通过 bridge 转移，但销毁仍必须走 bridge 规定的 Rust 侧逻辑，不能交给 C++ `delete`。

**规则**: 为每种对象明确唯一的销毁 API 与分配器边界。不要在 C++ 中直接 `delete` Rust 分配的对象，反之亦然；即使使用智能指针，也要确认最终析构发生在哪一侧、哪个线程，以及所用运行库是否匹配。

## 4. 技术挑战与“深水区” (The Deep Water)

迁移不仅是语言的转换，更是思维模式的冲突。以下是我们在实际迁移中遇到的最大技术障碍。

### 4.1 模板元编程 (Template Metaprogramming)
C++ 库常用模板表达编译期多态和接口约束，例如 CRTP、SFINAE 与 C++20 Concepts。编译器可以为具体类型生成代码，但代价可能包括代码体积和复杂的编译错误；“用了模板”也不保证一定内联或更快。
*   **挑战**: 绑定工具通常不能把任意模板定义原样暴露为 Rust 泛型。像 `OrderBook<NYSE>` 这样的具体实例，通常需要在 C++ 侧先实例化并包装成普通函数或不透明类型。
*   **解决**:
    *   **手动特化 (Manual Monomorphization)**: 在 C++ 侧写辅助函数，实例化特定类型的模板，导出为普通函数。
        下面只展示包装形状，`OrderBook`、`NYSE` 与 `Order` 由原项目提供，因此不是独立程序。
        ```cpp,ignore
        // C++ Side
        using NYSEBook = OrderBook<NYSE>;
        void process_nyse(NYSEBook& book, const Order& o) { book.add(o); }
        ```
    *   **Rust 泛型重写**: 如果逻辑不复杂，可用 Rust 泛型 + Trait 重写。Rust 与 C++ 模板的特化规则和可表达模式不同，应按实际实例集合验证，而不是逐语法翻译。

### 4.2 继承与虚函数 (Inheritance & Virtual Functions)
*   **挑战**: Rust 没有继承。如果 C++ 代码严重依赖类层次结构（如 `BaseStrategy -> MomentumStrategy`），很难直接映射。
*   **解决**:
    *   **组合优于继承**: 将基类逻辑提取为 `struct BaseContext`，作为成员包含在 Rust 结构体中。
    *   **Trait Object**: 将 C++ 的虚基类映射为 Rust 的 `dyn Trait`。`cxx` 支持调用 C++ 的虚函数，但需要小心生命周期。

### 4.3 异常安全 (Exception Safety)
这是最需要显式约定的边界之一。
*   **问题**: 不要让 C++ 异常或 Rust panic 穿过一个不允许 unwind 的 ABI 边界；具体结果取决于 ABI、编译选项与桥接工具，可能终止进程或触发未定义行为，不能依赖“另一侧会自动接住”。
*   **解决**:
    *   **C++ -> Rust**: 使用 `cxx` 时，把可能抛出的函数在 bridge 中声明为 `Result<T>`，CXX 才会捕获并转成 `Err`；未声明 `Result` 却抛出会走 `std::terminate`。原始 `extern "C"` 接口则应在 C++ wrapper 内捕获并转换成错误码。
    *   **Rust -> C++**: CXX 的 `extern "Rust"` 函数发生 panic 会 abort。一般 FFI 若需要把 panic 转成错误，应在导出边界内部处理 `catch_unwind`（只捕获 unwind panic），不要让它穿越不匹配 ABI；全局 `panic = "abort"` 会影响整个进程的恢复方式，必须与监督进程和风控策略一起设计。

如果系统明确选择全局 fail-stop，可以这样配置；这不是所有迁移项目的默认答案：

```toml
[profile.release]
panic = "abort"
```

### 4.4 编译与链接复杂性
*   **挑战**: 两个编译器（rustc, clang++）、两个构建系统（Cargo, CMake）、两个标准库（libc++, libstd）。符号冲突、ABI 不兼容、链接顺序错误是家常便饭。
*   **解决**: 固定并记录 Rust toolchain、C++ 编译器、目标 triple、C++ 标准库、链接器和编译 flags，在 CI 中构建最小跨语言 smoke test。普通 C ABI/静态库互调并不要求 C++ 编译器与 rustc 使用相同 LLVM；只有共享 LLVM bitcode 的跨语言 LTO 才会引入更严格的插件/bitcode 兼容要求。

### 4.5 性能陷阱：跨语言内联 (Cross-Language LTO)
默认情况下，语言边界通常会阻止跨边界内联，但实际成本取决于 ABI、参数传递、所有权转换、缓存行为和调用频率，没有可信的固定纳秒数。

建议按以下顺序优化：

1. **先做粗粒度接口**：把一批订单/行情一次交给另一侧处理，减少往返次数；
2. **建立基准**：在目标硬件分别测空调用、代表性 payload 和端到端路径，并查看生成汇编/调用栈；
3. **最后评估跨语言 LTO**：只有基准表明边界调用或无法内联确为瓶颈，才固定一套经过验证的 Clang/rustc/linker 组合尝试 `linker-plugin-lto`/ThinLTO；
4. **CI 验证兼容性**：执行全量链接、行为测试、sanitizer 与性能回归。工具链不兼容通常应在构建期失败，不能依赖“版本号看起来接近”来证明产物正确。

### 4.6 内存对齐 (Alignment)
Rust 的 `#[repr(Rust)]` 内存布局是不确定的。
按值或按字段共享布局的类型应使用双方约定的 ABI 表示（Rust 侧通常是 `#[repr(C)]`），并用两侧 `sizeof`、`alignof` 与字段 offset 的静态断言验证。若类型只通过不透明指针/句柄传递，则不需要向另一侧暴露内部布局。

```rust
#[repr(C)]
pub struct OrderWire {
    pub price_ticks: u64,
    pub quantity: u32,
    pub side: u8,
    pub reserved: [u8; 3],
}
```

不要默认 Rust `AtomicU64` 与 C++ `std::atomic<uint64_t>` 具有相同布局或 ABI；若要共享原子内存，需要单独定义并验证双方共同遵守的表示、对齐和内存模型协议。

## 5. 进阶技巧与最佳实践 (Advanced Techniques)

### 5.1 不透明句柄模式 (Opaque Handle Pattern)
当 C++ 和 Rust 需要共享一个对象（如 `std::shared_ptr<Context>`），但又不想暴露其内部布局时，使用此模式。

**C++ 侧 (`context_wrapper.h`)**：这是多文件 FFI 头文件，依赖项目中的 `legacy_context.h`，不能单独编译。
```cpp,ignore
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

下面的 Rust 声明必须与前一段 C++ 头文件共同构建，并依赖 `cxx` 生成代码；mdBook 因而不执行该多文件示例。

```rust,ignore
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

### 5.2 跨语言 LTO 的验证性配置
跨语言 LTO 是可选的后期优化，不是 FFI 正确性或低延迟的前提。下面只展示一种可能的配置方向，不能直接复制到所有工具链。

1.  **锁定已验证工具链**: 记录 `clang++`、`rustc -vV`、linker 与目标 triple；通过最小 bitcode 链接测试确认实际兼容性。
2.  **Rust 配置 (`Cargo.toml`)**:
    ```toml
    [profile.release]
    lto = "thin"
    codegen-units = 1
    ```
3.  **C++ 配置 (`CMakeLists.txt`)**:
    ```cmake
    # 使用 Clang 并开启 ThinLTO
    set(CMAKE_CXX_COMPILER "clang++")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -flto=thin")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -fuse-ld=lld -Wl,--plugin-opt=O3")
    ```

Rust 与 C++ 的跨语言 bitcode 链接还可能需要额外的 `-Clinker-plugin-lto`、crate 类型和 linker 配置；应以当前 rustc/LLVM 文档及可复现的 CI 原型为准。若收益不稳定，保留粗粒度 FFI 往往更易维护。

### 5.3 调试混合栈 (Debugging Mixed Stacks)
当程序崩溃时，你需要能看到跨语言的调用栈。
*   **工具**: 使用 `lldb` (macOS) 或 `gdb` (Linux)。Rust 自带的 `rust-lldb` / `rust-gdb` 包装器对 Rust 符号支持更好。
*   **技巧**: 编译时保留符号表。
    *   Rust: `[profile.release] debug = true`（保留优化同时生成调试信息；仍需验证最终产物大小、符号拆分与部署方式）。
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
**C++ 代码**：下面是结构骨架，省略了 `Context`、`Order`、`Tick` 和策略计算实现。
```cpp,ignore
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

以下四段代码共同组成一个 **迁移结构骨架**。为突出“组合 + Trait + 静态分发”的关系，示例有意省略 `Order`、`Tick`、行情来源和策略计算等业务实现；这些片段不是四个互相独立的程序，因此 mdBook 不执行它们。

1.  **提取公共状态 (Composition)**:
    不要继承 `Context`，而是包含它。该片段依赖本节共同的业务类型骨架，不单独测试。
    ```rust,ignore
    struct StrategyContext {
        // ... socket, logs, etc
    }
    
    impl StrategyContext {
        fn send_order(&mut self, order: Order) { ... }
    }
    ```

2.  **定义行为接口 (Trait)**:
    `Tick` 和 `StrategyContext` 来自共同骨架，该接口片段不单独测试。
    ```rust,ignore
    trait Strategy {
        fn on_tick(&mut self, tick: &Tick, ctx: &mut StrategyContext);
    }
    ```

3.  **具体实现 (Implementation)**:
    这里有意省略信号算法和订单构造细节，必须与共同骨架合并后才能编译。
    ```rust,ignore
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
    若具体策略类型在编译期已知，可以使用泛型 `T: Strategy`；若需要运行时加载异构策略，`Box<dyn Strategy>` 可能更合适。该引擎片段展示静态分发，并依赖共同骨架中的行情来源，所以不单独测试。
    ```rust,ignore
    struct Engine<S: Strategy> {
        context: StrategyContext,
        strategy: S, // 编译期确定的具体类型，无虚函数开销
    }
    
    impl<S: Strategy> Engine<S> {
        fn run(&mut self) {
            while let Some(tick) = self.context.next_tick() {
                // 静态分发让优化器有机会内联；是否真的内联要检查产物。
                self.strategy.on_tick(&tick, &mut self.context);
            }
        }
    }
    ```

这种 **Trait + Generic** 模式使用静态分发，能让优化器看见具体类型；它与 C++ 模板/CRTP 的目标相似。最终是否内联、代码体积是否膨胀，仍应通过产物和基准验证。

## 6. 常见面试题 (Q&A)

### Q1: 你们如何保证重构后的正确性？(Shadow Mode)
**问题背景**: 交易系统不能靠一次上线后的观察来证明迁移正确，需要可重复比较和可回滚切换。
**回答**:
"我们采用**影子模式 (Shadow Mode)** 并保留旧路径：
1.  **并行运行**: 在生产环境中，C++ 旧模块和 Rust 新模块同时接收市场数据。
2.  **只读不写**: Rust 模块执行所有计算逻辑，但**禁止发单**。它的输出（如定价、信号）被写入专门的日志或 RingBuffer。
3.  **实时比对**: 有一个旁路脚本（或专门的 Verify 线程）实时消费 C++ 和 Rust 的输出。
    *   **一致性**: 离散字段可逐位比较；浮点或时序相关结果先定义业务容差与不变量，避免把非确定差异误判为错误。
    *   **延迟**: 在同一输入、核绑定和时间戳口径下比较完整分位分布，而不是只看单次更快。
4.  **验收与灰度**: 覆盖历史回放、故障注入、极端行情和恢复流程；一致性阈值、观察窗口与回滚条件由业务风险预先定义，不套用固定天数或百分比。"

### Q2: 跨语言调用的开销有多大？如何优化？
**问题背景**: 很多人认为 FFI 很慢，不适合高频。
**回答**:
"FFI 没有统一的纳秒答案。先分别测空边界、真实参数和端到端请求，并确认是否发生字符串转换、分配或引用计数。优化顺序通常是：
1.  **Chunky Interface (粗粒度接口)**: 不要逐元素跨边界往返，而是借用 slice/批量结构，让另一侧内部循环；
2.  **稳定表示与所有权**: 使用固定宽度字段，明确谁分配、谁销毁，避免热路径隐式转换；
3.  **可选 LTO**: 只有 profile 表明调用边界确是瓶颈，才在锁定工具链后试验跨语言 LTO，并以汇编和回归基准确认收益；
4.  **共享内存**: 适合进程或组件传递大块数据，但需要单独证明生命周期、同步、对齐和崩溃恢复，绝不是‘绕过函数调用就自动安全’。"

### Q3: 如果 C++ 端发生了 Segfault，Rust 能救吗？
**问题背景**: Rust 标榜内存安全，但和 unsafe 的 C++ 混编时，这种保证还存在吗？
**回答**:
"**救不了**。Rust 的安全保证不能约束外部 C++ 实现。如果 C++ 破坏堆内存或访问野指针，可能立即触发进程级崩溃，也可能先静默破坏 Rust 依赖的内存不变量。
为了缓解这个问题，我们采取防御性编程：
1.  **Sanitizers**: 在兼容的测试构建中运行 ASan/UBSan 等工具，覆盖它们擅长检测的越界、释放后使用等错误；它们不能证明没有内存错误。
2.  **隔离 (Isolation)**: 如果某个遗留 C++ 模块非常不稳定，我们会把它拆分成独立的进程，通过共享内存（SHM）或 IPC 通信。这样它崩了只会重启它自己，不会拖垮主策略进程。
3.  **定义失败策略**: 根据订单状态与高可用架构选择 fail-stop、撤单/熔断和进程拉起策略。`panic = 'abort'` 是一种部署选择，不替代外部风控与恢复设计。"

### Q4: 怎么处理 C++ 的 `std::shared_ptr` 和 Rust 的 `Arc`？
**问题背景**: 两种语言都有引用计数，怎么互通？
**回答**:
"这是一个棘手的问题，因为它们的内存布局完全不同，原子操作的实现也不一定兼容。
通常做法是**不互通**，而是**持有句柄 (Opaque Handle)**：
*   **Rust 持有 C++**: Rust struct 中存放一个 `cxx::SharedPtr<CppClass>`。克隆的是 C++ `std::shared_ptr` 句柄并增加其控制块的强引用计数，不会调用 `CppClass` 对象的拷贝构造函数。
*   **C++ 持有 Rust**: Rust 可以导出一个不透明句柄，并把 clone、访问和 drop 都实现为 Rust 函数；C++ 只保存句柄，不能解释 `Arc` 的布局，也不能自行修改引用计数。
**更容易审计的做法**: 优先明确**单一所有权 (Single Ownership)**：要么由 C++ 拥有并在用完后通知 Rust，要么由 Rust 拥有并在一次调用期间借给 C++。如果业务确实要求共享，句柄表或对象池加代际 ID 是可选方案，但还要设计容量、失效句柄、同步和回收，不能当成普遍最优答案。"

### Q5: 如何证明迁移没有偷偷增加拷贝？

不要只回答“用了引用所以零拷贝”。应检查 bridge 生成代码与函数签名，分别记录分配次数、复制字节数和代表性 payload 的分位延迟；再用地址/生命周期测试确认借用没有被转换成临时 owned 对象。只有这些证据同时成立，才能把该条路径称为零拷贝。

权威参考：[rustc linker-plugin LTO](https://doc.rust-lang.org/stable/rustc/linker-plugin-lto.html)、[CXX `Result<T>` 与异常语义](https://cxx.rs/binding/result.html) 和 [Rustonomicon: FFI 与 unwinding](https://doc.rust-lang.org/nomicon/ffi.html#ffi-and-unwinding)。
