# 泛型与 Const Generics (Generics)

泛型（Generics）是 Rust 最强大的特性之一。对于初学者来说，它可能只是“代码复用”的工具，比如不用为 `i32` 和 `f64` 分别写两个加法函数。

但在 HFT 领域，泛型是实现**零成本抽象（Zero-Cost Abstractions）**的核心。这意味着我们可以写出像 Python 一样抽象、易读的代码，而编译器会把它编译成手写汇编一样高效的机器码。

## 1. 什么是单态化 (Monomorphization)？

Rust 的泛型实现策略叫做“单态化”。听起来很学术，其实原理非常简单：**编译器在编译时，会为每一个用到的具体类型，复制并生成一份专用的代码。**

### 举个栗子

假设我们有一个泛型函数：

```rust
fn print_item<T: std::fmt::Display>(item: T) {
    println!("Item: {}", item);
}

fn main() {
    print_item(42);      // 用 i32 调用
    print_item("hello"); // 用 &str 调用
}
```

在编译后，Rust 编译器实际上生成了两个完全不同的函数，就像你自己手写的一样：

```rust
// 编译器自动生成的代码（伪代码）
fn print_item_i32(item: i32) {
    println!("Item: {}", item);
}

fn print_item_str(item: &str) {
    println!("Item: {}", item);
}
```

### 优缺点分析
*   **优点（HFT 最爱）**：
    *   **极速**：因为函数是专门为 `i32` 生成的，编译器可以进行极致的优化（内联、常量折叠等）。运行时没有任何额外的类型检查开销。
*   **缺点**：
    *   **二进制膨胀**：如果你对 100 种类型调用了同一个泛型函数，二进制文件里就会有 100 个函数的副本。但在 HFT 中，为了速度，这点磁盘空间是完全值得的。

## 2. 静态分发 vs 动态分发：为什么要拒绝 `dyn Trait`？

在 Rust 中，实现多态有两种方式。初学者很容易混淆，但在性能上它们天差地别。

### 方式一：静态分发 (`impl Trait` 或泛型)

```rust
// 泛型：编译期确定类型
fn run_strategy<S: Strategy>(s: S) {
    s.on_tick();
}
```

这是我们推荐的方式。编译器知道 `s` 到底是什么类型，直接生成调用指令 `CALL 0x1234`。这是最快的。

### 方式二：动态分发 (`dyn Trait`)

```rust
// Trait Object：运行时确定类型
fn run_strategy_dyn(s: &dyn Strategy) {
    s.on_tick();
}
```

当你使用 `Box<dyn Strategy>` 或 `&dyn Strategy` 时，编译器在编译期不知道 `s` 具体是哪个 struct。它只知道 `s` 实现了 `Strategy`。

在运行时，程序必须：
1.  **查表**：通过“虚函数表（vtable）”指针找到 `on_tick` 函数的真实地址。
2.  **跳转**：跳转到那个地址执行。

### 为什么 HFT 讨厌 `dyn Trait`？
这就好比**打电话**：
*   **静态分发**：你把朋友的号码背下来了，拿起电话直接拨。
*   **动态分发**：你只知道要给“某个人”打电话，每次都要先翻电话簿（查 vtable），找到号码，再拨。

虽然查表很快（纳秒级），但在 HFT 中：
1.  **无法内联**：编译器没法把 `on_tick` 的代码内联进来，阻碍了后续优化。
2.  **缓存未命中**：vtable 可能不在 CPU 缓存（L1 Cache）中，去内存里读 vtable 可能会导致几十纳秒的延迟。
3.  **分支预测失败**：CPU 难以预测在这个间接跳转后会执行什么指令。

**结论**：在核心交易路径上，**严禁使用 `dyn Trait`**。

## 3. Const Generics：让数字成为类型的一部分

在 Rust 1.51 之前，如果你想写一个固定大小的数组包装器，非常痛苦。现在有了 Const Generics，我们可以把**值**当作泛型参数。

### 为什么需要它？
在 HFT 中，我们尽量避免使用 `Vec<T>`，因为 `Vec` 需要在堆上分配内存（慢）。我们更喜欢用数组 `[T; N]`（栈上分配，快）。

但如果我们想写一个通用的 RingBuffer，怎么指定数组大小呢？

```rust
// N 是一个 usize 类型的常量泛型参数
struct RingBuffer<T, const N: usize> {
    data: [T; N], // 数组大小由 N 决定
    head: usize,
    tail: usize,
}

impl<T, const N: usize> RingBuffer<T, N> {
    fn new() -> Self {
        // ...
    }
}

fn main() {
    // 创建一个容量为 1024 的缓冲区
    // 这个 1024 是编译期确定的，整个结构体都在栈上！
    let rb = RingBuffer::<i32, 1024>::new();
}
```

### 性能优势
1.  **零分配**：完全不需要 `malloc`，完全在栈（或静态区）上。
2.  **编译器优化**：因为 `N` 是常量，编译器可以做很多骚操作。例如，如果 `N` 是 2 的幂（如 1024），编译器会自动把取模运算 `% N` 优化成位运算 `& (N - 1)`，这比除法指令快几十倍。

## 4. 关联类型 vs 泛型 (Associated Types vs Generics)

这是一个经典的 Rust 面试题：**"什么时候用关联类型（`type Item`），什么时候用泛型（`<T>`）？"**

### 核心区别：唯一性

*   **泛型 (`trait Trait<T>`)**：意味着对于同一个类型，可以有**多个**实现。
*   **关联类型 (`trait Trait { type Item; }`)**：意味着对于一个类型，只能有**唯一**的一个实现。

### 案例分析

#### 1. `Iterator` 使用关联类型
```rust
pub trait Iterator {
    type Item; // 关联类型
    fn next(&mut self) -> Option<Self::Item>;
}
```
**原因**：对于一个特定的迭代器（比如 `vec.iter()`），它吐出的元素类型是确定的。不可能同一个迭代器一会儿吐出 `i32`，一会儿吐出 `String`。使用关联类型，编译器就知道 `Vec<i32>::iter()` 的 `Item` 只能是 `&i32`，不需要我们在调用 `next()` 时再指定类型。

#### 2. `Add` 使用泛型
```rust
pub trait Add<RHS = Self> {
    type Output;
    fn add(self, rhs: RHS) -> Self::Output;
}
```
**原因**：加法是多态的。
*   `Point` 可以加 `Point` (`impl Add<Point> for Point`)。
*   `Point` 也可以加 `i32` (`impl Add<i32> for Point`)。
*   我们希望同一个类型能实现多个不同版本的 `Add`。

### HFT 选型建议
在设计系统接口时：
*   如果某种输入与当前类型是**1对1绑定**的（比如 `Strategy` 绑定的 `Config`），用**关联类型**。这样接口更简洁，不需要到处写 `<C>`。
*   如果某种输入是**1对多**的（比如 `Strategy` 可以处理多种 `Event`），用**泛型**。

## 5. GATs: 泛型关联类型 (Generic Associated Types)

Rust 1.65 引入了一个划时代的特性：GAT (Generic Associated Types)。在此之前，我们很难用 Rust 表达“流式迭代器 (Streaming Iterator)”的概念。

### 痛点：标准 Iterator 的局限性

假设我们要实现一个高性能的市场数据解析器。我们要遍历一个巨大的 buffer，每次产生一个 `Packet` 结构体。为了零拷贝，`Packet` 内部持有 buffer 的引用。

```rust
struct PacketParser<'a> {
    buffer: &'a [u8],
    pos: usize,
}

struct Packet<'a> {
    data: &'a [u8], // 指向 Parser 内部的 buffer
}

// ❌ 编译错误！这是标准 Iterator 做不到的
// impl<'a> Iterator for PacketParser<'a> {
//     type Item = Packet<'? ?>; 
//     // Item 的生命周期无法与 next(&mut self) 中的 self 关联！
// }
```

标准 `Iterator` 假设产生的 `Item` 是**独立的**（Owned）或者是借用自**外部**的，但绝对不能借用迭代器**本身**。这导致我们必须拷贝数据，或者使用 `unsafe` 绕过生命周期检查。

### GAT 救场：流式迭代器 (Streaming Iterator)

GAT 允许我们在关联类型 `Item` 上添加泛型参数（生命周期）。

```rust
trait StreamingIterator {
    // 关键点：Item 带有一个生命周期参数 'a
    // 这个 'a 将会关联到 self 上
    type Item<'a> where Self: 'a;

    fn next<'a>(&'a mut self) -> Option<Self::Item<'a>>;
}

impl<'a> StreamingIterator for PacketParser<'a> {
    // 这里我们定义 Item<'b> 为 Packet<'b>
    type Item<'b> = Packet<'b> where Self: 'b;

    fn next<'b>(&'b mut self) -> Option<Self::Item<'b>> {
        // 简化的逻辑：返回 buffer 的切片
        if self.pos >= self.buffer.len() {
            return None;
        }
        let data = &self.buffer[self.pos..];
        self.pos += 100; // 假设每个包 100 字节
        Some(Packet { data })
    }
}
```

### HFT 实战意义

在处理通过 TCP 流进来的行情数据时，我们经常需要：
1.  读取 socket 到 buffer。
2.  解析 buffer 头部。
3.  **原地**（In-place）处理数据，不发生任何内存拷贝。
4.  处理完后，buffer 的这部分空间失效，可以被覆盖。

GAT 让我们可以定义这种“借用式”的接口，确保你在处理完当前包之前，不能请求下一个包（因为 `next` 借用了 `&mut self`，而返回的 `Item` 也借用了 `self`，生命周期重叠，编译器会阻止并发访问）。这完美契合了 Ring Buffer 的读写模式。

## 6. 总结

*   **泛型 = 复制粘贴**：Rust 为每个类型生成专门的代码（单态化），换取极致性能。
*   **关联类型 vs 泛型**：关联类型是**唯一**的（Iterator），泛型是**多态**的（Add）。
*   **拒绝动态分发**：在热路径上，永远优先使用 `impl Trait` 或泛型，避免 `dyn Trait` 带来的查表开销。
*   **Const Generics**：是构建高性能、定长、栈分配数据结构的神器。
*   **GAT**：解开了生命周期的枷锁，让我们可以实现真正的零拷贝流式处理。
