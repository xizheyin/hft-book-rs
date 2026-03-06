# 闭包与函数指针 (Closures & Function Pointers)

在 Rust 面试中，**"闭包 (Closure) 和函数指针 (fn pointer) 有什么区别？"** 以及 **"Fn, FnMut, FnOnce 到底怎么选？"** 是考察你是否真正理解 Rust 内存模型的试金石。

对于 HFT，这关乎**零分配 (Zero Allocation)** 和 **内联优化 (Inlining)**。

## 1. 闭包的本质：一个 Struct

在 C++ 或 Python 中，lambda 表达式可能看起来像魔法。但在 Rust 中，闭包**就是**一个普通的结构体 (Struct)。

```rust
let x = 10;
let add_x = |y| x + y;
```

编译器在背后悄悄生成了类似这样的代码：

```rust
struct ClosureEnvironment {
    x: i32, // 捕获了外部变量 x
}

impl ClosureEnvironment {
    fn call(&self, y: i32) -> i32 {
        self.x + y
    }
}
```

**面试考点**：闭包是有状态的（捕获了环境），而函数指针是无状态的（只是代码段的一个地址）。

## 2. 三大 Trait：`Fn` vs `FnMut` vs `FnOnce`

这三个 Trait 决定了闭包如何访问它捕获的环境变量。

### 2.1 `FnOnce`：一次性用品
*   **语义**：闭包会**消耗**（Move）掉捕获的变量。只能调用一次。
*   **例子**：
    ```rust
    let s = String::from("hello");
    let f = || drop(s); // s 被 move 进闭包了
    f(); // OK
    // f(); // ❌ 编译错误：s 已经被 drop 了，不能再用了
    ```
*   **底层**：`self` 是通过值 (`self`) 传入的。

### 2.2 `FnMut`：可变借用
*   **语义**：闭包会**修改**捕获的变量。可以多次调用。
*   **例子**：
    ```rust
    let mut count = 0;
    let mut f = || count += 1; // 捕获了 &mut count
    f();
    f();
    ```
*   **底层**：`self` 是通过可变引用 (`&mut self`) 传入的。

### 2.3 `Fn`：不可变借用
*   **语义**：闭包只**读取**捕获的变量，或者根本不捕获变量。可以并发多次调用。
*   **例子**：
    ```rust
    let x = 10;
    let f = || println!("{}", x); // 捕获了 &x
    f();
    ```
*   **底层**：`self` 是通过共享引用 (`&self`) 传入的。

**继承关系**：`Fn` : `FnMut` : `FnOnce`。
如果一个闭包实现了 `Fn`，它一定也实现了 `FnMut` 和 `FnOnce`。

## 3. 静态分发 vs 动态分发 (HFT 视角)

在 HFT 中，我们在设计回调函数（Callback）时，应该怎么写？

### ❌ 动态分发 (`Box<dyn Fn>`)
```rust
struct Strategy {
    // 这是一个指针（Fat Pointer），指向堆上的闭包
    on_tick: Box<dyn Fn(f64)>, 
}
```
*   **缺点**：
    1.  **堆分配**：`Box` 意味着 `malloc`。
    2.  **虚函数调用**：无法内联，只能间接跳转。
    3.  **缓存不友好**。

### ✅ 静态分发 (泛型)
```rust
struct Strategy<F> 
where 
    F: Fn(f64) 
{
    // 这是一个直接嵌入的 Struct（闭包环境）
    on_tick: F, 
}
```
*   **优点**：
    1.  **零分配**：闭包环境直接嵌入在 `Strategy` 结构体里。
    2.  **完全内联**：编译器知道 `F` 具体是哪个闭包，直接把代码内联进来。

## 4. 函数指针 `fn`：C 语言的遗产

`fn`（小写）是一个原生指针类型，指向代码段的某个地址。它**没有任何状态**（不能捕获变量）。

```rust
fn add_one(x: i32) -> i32 { x + 1 }

let f: fn(i32) -> i32 = add_one; // 这是一个 64 位的指针
```

### HFT 场景：极致优化
在极少数情况下，为了减小结构体体积（泛型单态化会导致代码膨胀），或者为了兼容 C FFI，我们会使用 `fn` 指针。

**面试陷阱**：如果不捕获变量，闭包可以被强制转换为 `fn` 指针吗？
**答**：可以！
```rust
let f: fn(i32) -> i32 = |x| x + 1; // ✅ 没捕获环境，可以转
// let y = 10;
// let g: fn(i32) -> i32 = |x| x + y; // ❌ 捕获了 y，无法转成 fn 指针
```

## 5. 总结

*   **闭包是 Struct**：捕获了环境的结构体。
*   **FnTrait 决定权限**：
    *   `FnOnce`: Move (吃掉环境)
    *   `FnMut`: `&mut` (修改环境)
    *   `Fn`: `&` (只读环境)
*   **HFT 准则**：
    *   能用泛型 (`F: Fn`) 就别用 `Box<dyn Fn>`。
    *   如果不需要捕获环境，优先用 `fn` 指针，因为它是体积最小的（只有一个指针大小）。
