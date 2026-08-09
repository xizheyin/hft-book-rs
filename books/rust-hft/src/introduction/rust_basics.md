# Rust 基础：从可运行程序到类型、模式与测试

Rust 的所有权和生命周期很重要，但初学者首先要能读懂一段普通程序：数据是什么类型，变量能否修改，分支返回什么，失败怎样表达，代码怎样拆成 module，最后怎样运行测试。本章先搭好这层语法与工程骨架；所有权的设计动机见[为什么选择 Rust](why_rust.md)，复杂生命周期、泛型和错误布局由后续专章主讲。

## 1. 一个 Rust 项目怎样运行

Cargo 是 Rust 官方的项目构建与包管理工具，它负责读取项目元数据、解析依赖、调用编译器和运行测试。安装 Rust 工具链后，可以让 Cargo 创建最小二进制项目：

```bash
cargo new hello_systems
cd hello_systems
cargo run
```

目录的核心部分是：

```text
hello_systems/
├── Cargo.toml   # package 元数据和依赖
└── src/
    └── main.rs  # 二进制入口
```

`src/main.rs` 可以只有：

```rust
fn main() {
    println!("hello, systems");
}
```

`fn` 声明函数，`main` 是普通二进制程序的入口，`println!` 末尾的 `!` 表示它是宏调用。这里使用宏，是因为格式化输出要接受数量和类型可变的参数；不需要先理解宏展开细节才能使用它。

常用命令各自回答不同问题：

| 命令 | 作用 |
|---|---|
| `cargo check` | 做类型检查等编译前端工作，通常比生成完整二进制快 |
| `cargo build` | 构建开发版本 |
| `cargo build --release` | 按 release profile 优化构建；结果通常位于 `target/release` |
| `cargo run` | 构建后运行当前二进制 |
| `cargo test` | 构建并执行测试 |
| `cargo fmt --check` | 检查格式是否符合 rustfmt |
| `cargo clippy -- -D warnings` | 运行常用 lint（静态代码检查规则），并把 warning 当作失败 |

“能编译”只表示满足编译器检查，不表示业务规则正确；“Debug 很慢”也不能推出 Release 一定正确。正确性由类型、不变量与测试共同建立，性能要在可复现的 Release 环境测量。

## 2. `let` 创建绑定，`mut` 允许重新修改

Rust 变量默认不可修改：

```rust
fn main() {
    let limit = 100_u64;
    let mut accepted = 0_u64;

    if accepted < limit {
        accepted += 1;
    }

    assert_eq!(accepted, 1);
}
```

`100_u64` 明确表示无符号 64 位整数。`accepted` 前有 `mut`，所以可以执行 `+= 1`。默认不可变能让读者和编译器更容易判断值是否会变化；需要累加、更新状态时再明确写 `mut`。

### 2.1 Shadowing 不是修改同一类型的槽位

Rust 允许用新的 `let` 遮蔽同名旧绑定：

```rust
fn main() {
    let text = "42";
    let text = text.len();
    assert_eq!(text, 2_usize);
}
```

第二个 `text` 是新绑定，类型从 `&str` 变成 `usize`。`mut` 则表示同一绑定可以重新赋值，重新赋的值仍需符合它的类型。二者不要混为一谈。

## 3. 常用基本类型及其边界

| 类型 | 表示什么 | 常见注意点 |
|---|---|---|
| `bool` | `true` 或 `false` | 不与整数隐式互换 |
| `i8`…`i128` | 固定位数有符号整数 | 范围外转换与算术溢出要明确处理 |
| `u8`…`u128` | 固定位数无符号整数 | 不能表示负数，不应仅为了“更大范围”乱用 |
| `isize` / `usize` | 与目标指针宽度相关的整数 | `usize` 常用于下标和长度，不等于业务金额类型 |
| `f32` / `f64` | IEEE 754 浮点数 | 许多十进制小数不能精确表示，`NaN` 也破坏普通全序直觉 |
| `char` | 一个 Unicode scalar value | 固定 4 字节，不等于一个用户看到的完整字符 |
| `()` | unit，表示没有有意义返回值 | 类似“完成动作但不返回业务数据” |

Rust 不做多数危险的隐式数值转换。下面用 `try_from` 明确检查范围：

```rust
use std::convert::TryFrom;

fn main() {
    let packet_len: u64 = 1500;
    let index = usize::try_from(packet_len).expect("packet length must fit usize");
    assert_eq!(index, 1500);
}
```

`as` 可以执行显式数值转换，但某些转换会截断或改变含义。外部输入、金额、长度和协议字段优先使用 `try_from`、`checked_add`、`checked_mul` 等能暴露失败的接口。

整数在 Debug 和 Release 中的溢出行为配置可能不同，不能依赖“本地恰好 panic”作为业务校验。需要拒绝溢出的规则应显式检查。

## 4. `String` 与 `&str` 解决不同所有权问题

```rust
fn byte_len(text: &str) -> usize {
    text.len()
}

fn main() {
    let owned = String::from("hello");
    let literal: &str = "world";

    assert_eq!(byte_len(&owned), 5);
    assert_eq!(byte_len(literal), 5);
}
```

- `String` 拥有一段可增长的 UTF-8 字节缓冲区；离开所有者作用域时会自动清理；
- `&str` 是对一段有效 UTF-8 文本的借用视图，本身不拥有底层字节；
- `String` 可以借用为 `&str`，所以只读函数通常接收 `&str`，让调用者既能传字符串字面量，也能传已有 `String`。

`str::len()` 返回 UTF-8 **字节数**，不保证等于用户看到的字符数：

```rust
fn main() {
    assert_eq!("中".len(), 3);
    assert_eq!("中".chars().count(), 1);
}
```

直接用整数下标访问 `String` 会把 UTF-8 字节边界误当字符边界，所以 Rust 不提供 `text[0]` 这种普通字符串索引。处理协议原始字节时使用 `&[u8]`；处理 Unicode scalar value 时使用 `.chars()`；“用户看到的字形”还需要更高层 Unicode 分段规则。

## 5. 表达式可以产生值

Rust 的 `if`、代码块和 `match` 都可以返回值。代码块末尾没有分号的表达式就是该块的值：

```rust
fn classify(value: i32) -> &'static str {
    if value < 0 {
        "negative"
    } else if value == 0 {
        "zero"
    } else {
        "positive"
    }
}

fn main() {
    assert_eq!(classify(-3), "negative");
}
```

若给末尾表达式加分号，它就成为语句，代码块通常返回 `()`。这也是初学者常见类型错误来源：函数声明返回 `i32`，最后却写成 `value;`。

三类循环用途不同：

```rust
fn main() {
    let values = [2, 4, 6];
    let mut sum = 0;

    for value in values {
        sum += value;
    }

    let mut countdown = 2;
    while countdown > 0 {
        countdown -= 1;
    }

    let result = loop {
        if sum == 12 {
            break sum / 3;
        }
    };

    assert_eq!(result, 4);
}
```

- `for` 遍历迭代器，适合按元素处理；
- `while` 在条件为真时重复；
- `loop` 表示无条件循环，可用 `break value` 返回结果。

## 6. 所有权入门：先问谁负责清理

一个值通常有一个负责清理它的所有者。把拥有资源的值赋给另一个变量时，默认可能发生 move（移动），即清理责任转移，而不是复制缓冲区：

```rust
fn consume(text: String) -> usize {
    text.len()
}

fn main() {
    let message = String::from("done");
    let len = consume(message);
    assert_eq!(len, 4);
    // message 的所有权已经交给 consume，不能再使用。
}
```

函数只需查看时，使用借用：

```rust
fn inspect(text: &str) -> usize {
    text.len()
}

fn main() {
    let message = String::from("done");
    assert_eq!(inspect(&message), 4);
    assert_eq!(message, "done");
}
```

常见基本整数实现 `Copy`，赋值会复制值，因此旧名字仍可用。`String` 拥有堆缓冲，默认不实现 `Copy`。不要用“在栈上就 Copy、在堆上就 move”判断；真正依据是类型实现的语义。

可变借用 `&mut T` 允许修改被借用值。在同一使用区间内，Rust 防止一个可变借用与其他会造成冲突的借用并存：

```rust
fn add_suffix(text: &mut String) {
    text.push_str("-ok");
}

fn main() {
    let mut status = String::from("ready");
    add_suffix(&mut status);
    assert_eq!(status, "ready-ok");
}
```

这一节只建立“所有者—借用者—清理责任”的入口。move、borrow、生命周期为何能防止悬空引用，见[为什么选择 Rust](why_rust.md)；复杂接口见[所有权与生命周期进阶](../rust_advanced/lifetimes.md)。

## 7. `struct` 组合字段，`enum` 表达有限状态

```rust
#[derive(Debug, PartialEq)]
struct Request {
    id: u64,
    payload: String,
}

impl Request {
    fn payload_len(&self) -> usize {
        self.payload.len()
    }
}

fn main() {
    let request = Request {
        id: 7,
        payload: String::from("ping"),
    };
    assert_eq!(request.payload_len(), 4);
}
```

`struct` 把同时存在的字段组合成一种类型。`impl` 块为类型定义关联函数或方法；`&self` 表示只借用当前对象。

`enum` 的每个变体可以携带不同数据，所以它适合表达状态与结果：

```rust
#[derive(Debug, PartialEq)]
enum JobState {
    Pending,
    Running { worker: String },
    Failed(String),
    Succeeded,
}

fn describe(state: &JobState) -> &str {
    match state {
        JobState::Pending => "pending",
        JobState::Running { worker } if worker.is_empty() => "running-without-worker",
        JobState::Running { .. } => "running",
        JobState::Failed(reason) if reason.is_empty() => "failed-without-reason",
        JobState::Failed(_) => "failed",
        JobState::Succeeded => "succeeded",
    }
}

fn main() {
    let state = JobState::Running {
        worker: String::from("worker-1"),
    };
    assert_eq!(describe(&state), "running");
}
```

`match` 必须覆盖所有可能变体。`_` 可匹配剩余情况，但若滥用它，新加状态可能被悄悄归入旧逻辑；关键状态机优先逐项写清。

`Option<T>` 是标准库 enum，表达“有一个 `T` 或没有值”；`Result<T,E>` 表达“成功得到 `T` 或失败得到 `E`”。它们把缺失和失败写入类型，不需要用 `-1`、空字符串或空指针混充状态。

```rust
fn parse_port(text: &str) -> Result<u16, String> {
    let port = text
        .parse::<u16>()
        .map_err(|error| format!("invalid port {text:?}: {error}"))?;

    if port == 0 {
        return Err(String::from("port must not be zero"));
    }
    Ok(port)
}

fn main() {
    assert_eq!(parse_port("8080"), Ok(8080));
    assert!(parse_port("0").is_err());
}
```

`?` 在 `Result` 为 `Err` 时提早返回，并按接口规则转换错误；它不是忽略错误。完整失败分类、panic 和错误成本见[错误处理](../rust_advanced/error_handling.md)。

## 8. Trait 描述能力，泛型使用能力

```rust
trait ByteSize {
    fn byte_size(&self) -> usize;
}

impl ByteSize for String {
    fn byte_size(&self) -> usize {
        self.len()
    }
}

fn total_size<T: ByteSize>(values: &[T]) -> usize {
    values.iter().map(ByteSize::byte_size).sum()
}

fn main() {
    let values = vec![String::from("ab"), String::from("c")];
    assert_eq!(total_size(&values), 3);
}
```

Trait 是一组行为约束：实现 `ByteSize` 的类型必须提供 `byte_size`。泛型函数 `total_size<T: ByteSize>` 不关心 `T` 的全部内部字段，只要求它具备该能力。

泛型常通过单态化为具体类型生成代码；`dyn Trait` 则允许运行时动态分发。二者的接口和成本由[泛型、分发与 GAT](../rust_advanced/generics.md)主讲。入门时先学会让 Trait 表达真正需要的最小能力，不要为“以后可能有用”设计巨大接口。

## 9. Module 控制名字与可见性

下面在一个文件中定义 module：

```rust
mod validation {
    pub fn non_empty(text: &str) -> bool {
        !text.is_empty()
    }

    fn internal_rule() -> bool {
        true
    }

    pub fn all_rules(text: &str) -> bool {
        non_empty(text) && internal_rule()
    }
}

fn main() {
    assert!(validation::all_rules("data"));
}
```

module 组织名字并控制可见性；条目默认私有，`pub` 才允许外部路径访问。项目变大后可把 module 放入其他文件，但 module 路径与文件系统路径不是“看到同名目录就自动全部导入”的关系，入口仍由 `mod`、`use` 和 package target 结构决定。

需要分清：

- **package** 由一份 `Cargo.toml` 描述，可包含多个构建 target；
- **crate** 是一次编译形成的库或二进制单元；
- **module** 是 crate 内部的命名与可见性结构；
- `use` 把路径引入当前作用域，它不会复制代码或对象。

依赖、feature、registry 与 `Cargo.toml` 的选择见[项目工具与依赖](ecosystem.md)。

## 10. 集合与迭代器：先写数据流，再看分配

最常用的拥有型集合包括：

- `Vec<T>`：连续、可增长序列；
- `String`：有效 UTF-8 字节序列；
- `HashMap<K,V>`：键值映射；
- `HashSet<T>`：不重复值集合；
- `VecDeque<T>`：适合两端操作的队列。

```rust
use std::collections::HashMap;

fn main() {
    let events = ["ok", "error", "ok"];
    let mut counts = HashMap::new();

    for event in events {
        *counts.entry(event).or_insert(0_u64) += 1;
    }

    assert_eq!(counts.get("ok"), Some(&2));
}
```

`entry` 把“查找键”和“若不存在则插入”组织成一次 map 接口操作。它不自动使整个 `HashMap` 能被多线程同时修改；并发还需要所有权分片、锁或消息传递。

迭代器把处理步骤串成惰性数据流：

```rust
fn main() {
    let values = [1_i32, 2, 3, 4];
    let doubled_even: Vec<i32> = values
        .iter()
        .copied()
        .filter(|value| value % 2 == 0)
        .map(|value| value * 2)
        .collect();

    assert_eq!(doubled_even, vec![4, 8]);
}
```

`.iter()` 借用元素，`.copied()` 将 `Copy` 元素复制成值，`filter` 选择，`map` 转换，`collect` 才真正构造 `Vec`。迭代器组合通常可被优化，但“用了迭代器就绝无分配”仍然错误：本例的最终 `Vec` 就会分配容量。闭包捕获与 `Fn` Trait 见[闭包与函数指针](../rust_advanced/closures.md)。

## 11. 测试把规则变成可执行证据

Rust 测试函数用 `#[test]` 标记，普通单元测试可以与被测 module 放在同一文件：

```rust
fn checked_total(values: &[u64]) -> Option<u64> {
    values
        .iter()
        .try_fold(0_u64, |sum, value| sum.checked_add(*value))
}

#[cfg(test)]
mod tests {
    use super::checked_total;

    #[test]
    fn sums_normal_values() {
        assert_eq!(checked_total(&[2, 3, 5]), Some(10));
    }

    #[test]
    fn rejects_overflow() {
        assert_eq!(checked_total(&[u64::MAX, 1]), None);
    }
}
```

`#[cfg(test)]` 表示这个 module 只在测试配置中编译。测试可使用 `assert!`、`assert_eq!` 和 `assert_ne!`。返回 `Result<(), E>` 的测试还可以使用 `?` 传播准备阶段的失败。

测试至少覆盖正常、边界和非法三类输入。对状态机还要覆盖不允许的转换；对并发代码要验证交错与不变量，而不是依赖一次运行恰好没出错。更完整的分层、故障注入和属性测试见[单元测试与集成测试](../testing/unit_integration.md)与[模糊测试与属性测试](../testing/fuzzing.md)。

## 12. 常见误区

1. **“变量默认不可变，所以对象绝不变化。”** 内部可变性、锁和原子类型可以在共享引用下受控修改；普通入门代码仍要先看具体类型接口。
2. **“Shadowing 就是 `mut`。”** 前者创建新绑定并可改变类型，后者修改原绑定且类型不变。
3. **“`String::len()` 是字符数。”** 它是 UTF-8 字节数。
4. **“所有赋值都会 move。”** 实现 `Copy` 的类型会复制值；其他拥有型值通常转移所有权。
5. **“引用一定不会为空，所以永远有效。”** Safe Rust 让合法引用满足有效性规则，但裸指针、FFI 与 `unsafe` 需要调用者证明额外条件。
6. **“`Option` 和 `Result` 只是让代码更长。”** 它们把缺失与失败变成必须处理的类型分支，避免魔法值混入正常数据。
7. **“`match _` 最省事。”** 它可能在新增 enum 变体时吞掉本应显式处理的状态。
8. **“Trait 就是传统面向对象的父类。”** Trait 描述能力，可用于静态或动态分发，不要求共享字段布局。
9. **“迭代器一定零成本、零分配。”** 优化要看具体适配器、收集目标和生成代码。
10. **“测试通过就没有 panic 或并发问题。”** 测试只覆盖实际运行的输入和交错，仍需类型约束、审查与专门工具。

## 13. 做题方法：沿类型和所有权逐行记账

1. 为每个表达式写类型；遇到 `if`、`match` 和代码块时，检查所有分支是否产生兼容类型。
2. 为拥有型值标记 owner；函数调用处写“move、共享借用 `&`、可变借用 `&mut` 或 Copy”。不要只凭变量名猜。
3. enum 题先列全部变体和携带数据，再写允许的模式；关键状态不要过早用 `_` 合并。
4. `Option` / `Result` 题逐层标出 `Some/None` 或 `Ok/Err`；看到 `?` 就写明哪个错误会从当前函数返回。
5. 集合题同时写元素类型、操作复杂度和引用失效条件。`Vec` 扩容可能移动缓冲区，所以不能跨潜在扩容长期保留内部引用。
6. 迭代器题从输入所有权开始：`.iter()`、`.iter_mut()`、`.into_iter()` 分别借用、可变借用或消费什么；最后是否 `collect` 决定是否构造结果集合。
7. 编译错误先读第一条主错误和标出的生命周期/类型位置，做最小修改验证理解；不要一开始靠 `clone()` 或 `unsafe` 压掉约束。

## 14. 章末思考题与代码题

1. `let x = 5; let x = x.to_string();` 使用了 `mut` 吗？两个 `x` 的类型分别是什么？
2. `String`、`&str` 与 `&[u8]` 分别适合表达什么？
3. 为什么函数最后的 `value` 和 `value;` 可能得到不同返回类型？
4. `let b = a;` 之后 `a` 能否继续使用，应根据什么判断？
5. `Option<T>` 与返回 `-1` 表示“没有结果”相比有什么优势？
6. `match` 为什么要求穷尽？什么时候 `_` 可能掩盖错误？
7. Trait bound `T: ByteSize` 向调用者和实现者分别承诺什么？
8. package、crate 和 module 有什么区别？`use` 会不会复制代码？
9. `.iter()`、`.iter_mut()` 和 `.into_iter()` 的所有权区别是什么？
10. 为累加 `u64` 的函数设计正常、空输入和溢出三类测试。为什么只测 `[1,2,3]` 不够？

### 参考答案与解答

<details>
<summary>展开答案</summary>

1. 没有使用 `mut`，而是 shadowing。第一个 `x` 由整数文字推断为整数类型；结合 `to_string` 可得到字符串，第二个 `x` 是 `String`。两次 `let` 创建不同绑定，所以允许类型改变。
2. `String` 拥有可增长 UTF-8 缓冲；`&str` 借用有效 UTF-8 文本，适合只读参数和切片；`&[u8]` 借用任意字节，适合协议帧、文件块和不保证 UTF-8 的数据。选择首先由数据语义和所有权决定，不由“哪个更快”单独决定。
3. 末尾无分号的表达式是代码块的值，因此 `value` 可返回 `value` 的类型；`value;` 是执行后丢弃结果的语句，块通常得到 `()`。若函数签名要求其他类型，编译器会报告不匹配。
4. 看 `a` 的类型是否实现 `Copy`，以及右侧操作是否只借用。`u64` 这类 Copy 值赋给 `b` 后 `a` 仍可用；`String` 默认发生 move，`a` 的清理责任交给 `b`，旧绑定不能继续用。不能用“栈/堆”口诀替代类型语义。
5. `Option<T>` 让类型系统强制区分 `Some(value)` 与 `None`，不会把合法的 `-1` 和缺失混在一起；它可与模式匹配、组合器和 `?` 共同工作。调用者必须显式决定缺失时怎么办。
6. enum 以后可能增加或当前已有多个状态；穷尽检查保证每种值都有处理路径。`_` 合并剩余值很方便，但状态机新增 `Cancelled` 时，旧 `_ => retry` 可能错误重试已取消任务。关键业务分支应逐项列出。
7. 对调用者，它说明 `total_size` 只接受实现 `ByteSize` 的元素；对泛型函数实现者，它保证可对 `T` 调用 Trait 中声明的方法，而不能擅自访问未知字段。具体类型负责提供满足语义的实现。
8. package 是 `Cargo.toml` 描述的发布/构建项目；crate 是一次编译的库或二进制单元；module 是 crate 内组织路径和可见性的结构。`use` 只是把路径引入当前作用域，不复制源代码，也不创建运行时对象。
9. `.iter()` 产生共享借用 `&T`；`.iter_mut()` 产生独占可变借用 `&mut T`；`.into_iter()` 消费接收者并按该类型的 `IntoIterator` 规则产生元素。对拥有的 `Vec<T>`，它通常移出 `T`；调用后原 `Vec` 不能再使用。
10. 可设计：`checked_total(&[2,3]) == Some(5)`；`checked_total(&[]) == Some(0)`；`checked_total(&[u64::MAX,1]) == None`。第一例只证明普通加法路径；空输入检查初始值定义，溢出例检查函数没有回绕、panic 或返回错误总数。三类测试对应正常、边界与非法/不可表示结果。

</details>

## 15. 本章小结

- Cargo 负责项目构建与测试；编译通过不等于业务正确。
- `let` 创建绑定，`mut` 修改原绑定，shadowing 创建同名新绑定。
- 数值、文本和字节类型有不同边界，转换与溢出要显式处理。
- `String` 拥有文本缓冲，`&str` 是借用视图，`&[u8]` 表示原始字节。
- 表达式产生值；分号会改变代码块的结果。
- 所有权题先追踪清理责任，再区分 move、borrow 与 Copy。
- `struct` 组合同时存在的数据，`enum` 表达有限分支与状态。
- Trait 描述能力；module 组织名字；集合与迭代器表达数据流。
- 测试覆盖正常、边界与失败路径，不能只证明一个示例能运行。

## 一手资料

- [The Rust Programming Language](https://doc.rust-lang.org/book/)：变量、类型、所有权、struct、enum、module、集合、泛型与测试的官方入门教材。
- [Rust Reference](https://doc.rust-lang.org/reference/)：表达式、类型、模式、可见性和其他语言规则的规范入口。
- [Cargo Book](https://doc.rust-lang.org/cargo/)：package、target、依赖、profile 与构建命令。
- [Rust Standard Library](https://doc.rust-lang.org/std/)：`Option`、`Result`、集合、迭代器与数值检查接口。
- [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/)：公共类型和 Trait 接口的惯例与检查清单。
