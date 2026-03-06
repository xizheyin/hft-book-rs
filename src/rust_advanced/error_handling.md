# 错误处理最佳实践 (Error Handling)

在 Java 或 Python 中，我们习惯用 `try-catch` 来捕获异常。
在 Rust 中，没有异常（Exception）。所有的可恢复错误都是**值（Value）**。

这意味着错误处理不是什么特殊的魔法，它只是普通的 `if-else` 或 `match` 逻辑。这种显式处理虽然写起来繁琐，但对于追求极致稳定性的 HFT 系统至关重要——**我们必须清楚地知道每一行代码会不会失败，以及失败了该怎么办。**

## 1. `Result<T, E>`：成败在此一举

Rust 的错误处理核心是 `Result` 枚举：

```rust
enum Result<T, E> {
    Ok(T),  // 成功，带回结果 T
    Err(E), // 失败，带回错误原因 E
}
```

### HFT 视角：Result 的内存开销与优化

因为 `Result` 是一个枚举，它的大小取决于**最大的那个成员**。
`sizeof(Result<T, E>) = max(sizeof(T), sizeof(E)) + 标签大小(通常1字节)`。

**新手陷阱**：
如果你定义了一个巨大的错误类型（比如包含了详细的堆栈信息字符串），那么即使函数成功了，返回 `Ok(T)` 时也必须复制那么大的内存（因为编译器要在栈上预留足够空间）。

```rust
// ❌ 错误示范
struct HugeError {
    msg: [u8; 1024], // 1KB
}

// 即使成功返回 4 字节的 i32，栈上也必须分配 1028 字节！
// 每次函数返回都会导致 1KB 的 memcpy，这是巨大的性能杀手。
fn process() -> Result<i32, HugeError> {
    Ok(42)
}
```

**HFT 准则**：
1.  **错误类型要极小**：在热路径上，用简单的 `enum` (1-8字节) 或单元结构体 `struct Error;` (0字节) 作为 `E`。
2.  **大错误放在堆上**：如果必须返回详细信息，使用 `Box<HugeError>`。虽然构造错误变慢了（需要 malloc），但**成功路径**变快了（Result 只有指针大小）。因为 HFT 假设 99.99% 的情况都是成功的。
3.  **利用 Niche Optimization**：Rust 编译器非常聪明。如果 `T` 有无效的位模式（例如 `&T` 永远不可能是 NULL），编译器会利用这个“空位”来存储 `Result` 的标签。
    *   `sizeof(Option<&T>) == sizeof(&T)` (8字节)。
    *   `sizeof(Result<&T, ()>) == sizeof(&T)` (8字节)。
    *   这意味着返回 `Option<&Order>` 和直接返回指针 `&Order` 的开销是**完全一样**的！这是真正的零成本抽象。

## 2. `?` 操作符：优雅的语法糖

在 Rust 代码中，你随处可见 `?`。它不是什么魔法，只是 `match` 的简写。

```rust
// 写法 A：使用 ?
fn read_price() -> Result<f64, Error> {
    let s = read_string()?;
    let p = parse_price(s)?;
    Ok(p)
}

// 写法 B：展开后（编译器的真实逻辑）
fn read_price() -> Result<f64, Error> {
    let s = match read_string() {
        Ok(val) => val,
        Err(e) => return Err(e), // 遇到错误，直接提前返回
    };

    let p = match parse_price(s) {
        Ok(val) => val,
        Err(e) => return Err(e),
    };

    Ok(p)
}
```

### 性能分析
现代 CPU 的**分支预测器（Branch Predictor）**非常聪明。它会发现 `return Err(e)` 这条路几乎从来不走。所以，`?` 在汇编层面通常会被优化成一条极快的测试指令，**在成功路径上几乎没有开销**。

## 3. Panic：Unwind vs Abort

当发生不可恢复的错误（比如数组越界、除以零）时，Rust 线程会 **Panic**。

Panic 有两种策略：

### 策略 A：Unwind（默认）
就像电影倒带一样。Rust 会沿着调用栈一层层往回退，每退一层，就运行那一层变量的析构函数（Drop），释放资源（比如关闭文件、释放内存）。
*   **优点**：资源清理干净，其他线程可能还能活。
*   **缺点**：生成的二进制代码大（包含大量“倒带”逻辑），Panic 发生时处理慢。

### 策略 B：Abort（HFT 推荐）
就像**直接拔电源**。进程立即终止，操作系统回收所有资源。
*   **优点**：二进制极小，代码生成简单，确定性强。
*   **缺点**：进程直接挂了。

### 为什么 HFT 选择 Abort？
1.  **速度**：我们不需要 Unwinding 的额外指令干扰 CPU 缓存。
2.  **安全**：如果 HFT 系统内部状态错乱（Panic 了），最安全的做法是**立即停止一切**，而不是试图清理并继续（可能会发出错误的巨额订单）。让外部的看门狗（Watchdog）进程把我们重启，从干净的状态恢复，反而更安全。

**配置方法**：
在 `Cargo.toml` 中：
```toml
[profile.release]
panic = 'abort'
```

## 4. 总结

*   **Result 是值**：错误处理就是处理返回值。注意控制错误类型的大小。
*   **? 是语法糖**：它会被编译成高效的分支指令，不用担心性能。
*   **Panic = Abort**：在 HFT 中，遇到无法处理的错误直接崩溃是更安全、更高效的选择。
