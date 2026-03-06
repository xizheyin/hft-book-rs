# 宏编程实战 (Macros)

在其他语言（如 C++）中，宏往往被视为“危险”或“晦涩”的代名词。但在 Rust 中，宏是**安全且强大**的工具。

对于 HFT 开发者来说，宏不是为了炫技，而是为了**让编译器帮我们写那些重复、枯燥且高性能的代码**。

## 1. 什么是宏？它和函数有什么区别？

简单来说，**函数是运行时的逻辑，宏是编译期的逻辑**。

*   **函数**：接收参数 -> 运行代码 -> 返回结果。
*   **宏**：接收源代码 -> 修改/生成源代码 -> 交给编译器编译。

### 为什么 `println!` 必须是宏？
你想过为什么 `println!("hello {}", name)` 可以接受任意数量的参数吗？普通的 Rust 函数是做不到的。
宏可以！因为它在编译前会把这行代码“展开”成一大坨真正的 Rust 代码，处理好所有的参数格式化。

## 2. 声明宏 (`macro_rules!`)：模式匹配神器

声明宏有点像正则表达式：你定义一种“模式”，如果代码匹配这个模式，就把它替换成你想要的样子。

### 入门实例：简化版 `vec!`
假设我们要自己实现一个 `my_vec!`：

```rust
macro_rules! my_vec {
    // 模式：匹配一个表达式 ($x)，重复 0 次或多次 (*)，中间用逗号分隔 (,)
    ( $( $x:expr ),* ) => {
        {
            let mut temp_vec = Vec::new();
            // 对每一个匹配到的 $x，生成一行 push 代码
            $(
                temp_vec.push($x);
            )*
            temp_vec
        }
    };
}

fn main() {
    // 写的时候：
    let v = my_vec![1, 2, 3];
    
    // 宏展开后（编译器真正看到的代码）：
    /*
    let v = {
        let mut temp_vec = Vec::new();
        temp_vec.push(1);
        temp_vec.push(2);
        temp_vec.push(3);
        temp_vec
    };
    */
}
```

### HFT 实战：批量生成存取器
在处理二进制协议时，我们经常要解析几十个字段。手写几十个 getter 函数既累又容易错。

```rust
macro_rules! binary_field {
    // $name: 方法名 (ident = 标识符)
    // $ty:   返回类型 (ty = 类型)
    // $off:  偏移量 (expr = 表达式)
    ($name:ident, $ty:ty, $off:expr) => {
        #[inline(always)]
        pub fn $name(&self) -> $ty {
            // 直接读取内存，极其高效
            unsafe {
                let ptr = self.buffer.as_ptr().add($off);
                std::ptr::read_unaligned(ptr as *const $ty)
            }
        }
    };
}

struct MdHeader<'a> { buffer: &'a [u8] }

impl<'a> MdHeader<'a> {
    // 一行代码生成一个高性能 getter
    binary_field!(seq_num,   u64, 0);
    binary_field!(timestamp, u64, 8);
    binary_field!(msg_type,  u16, 16);
}
```

## 3. 过程宏 (Procedural Macros)：编译器插件

当 `macro_rules!` 不够用时（比如你需要读取外部文件、进行复杂的逻辑判断），就需要**过程宏**。
你可以把过程宏想象成一个**编译器插件**：Rust 编译器在编译过程中，会暂停一下，把一段代码交给你的宏程序处理，你的宏程序吐出新的代码，编译器再继续。

### 三种类型
1.  **派生宏 (Derive Macros)**: `#[derive(Serialize)]`
2.  **属性宏 (Attribute Macros)**: `#[tokio::main]`
3.  **函数宏 (Function-like Macros)**: `sql!("SELECT * FROM users")`

### HFT 终极应用：SBE 协议生成器

在 HFT 中，交易所通常提供 XML 格式的协议描述文件（如 FIX SBE）。手动照着 XML 写 Rust 结构体太蠢了。

我们可以写一个派生宏，**直接读取 XML，自动生成 Rust 代码**。

#### 输入：XML 描述
```xml
<message id="1" name="OrderAdded">
    <field name="OrderId" id="1" type="u64" offset="0"/>
    <field name="Price" id="2" type="u64" offset="8"/>
</message>
```

#### 使用宏
```rust
#[derive(SbeMessage)] // 调用我们的过程宏
#[sbe(file = "schema.xml", id = 1)]
struct OrderAdded<'a> {
    buffer: &'a [u8],
}
```

#### 输出：自动生成的代码（编译期）
我们的宏会去读取 `schema.xml`，找到 id=1 的消息，解析出它有两个字段，然后生成：

```rust
impl<'a> OrderAdded<'a> {
    pub fn order_id(&self) -> u64 {
        // 宏自动计算出 offset 是 0
        unsafe { ... }
    }
    
    pub fn price(&self) -> u64 {
        // 宏自动计算出 offset 是 8
        unsafe { ... }
    }
}
```

这不仅节省了时间，更重要的是**零运行时开销**。所有的偏移量计算都在编译期完成了，运行时只是几条简单的汇编指令。

## 4. 总结

*   **宏是代码生成器**：它在编译期运行，把简短的代码变成复杂的 Rust 代码。
*   **声明宏**：用模式匹配解决简单的重复代码（如 getter/setter）。
*   **过程宏**：像编译器插件一样强大，可以读取外部文件（XML/JSON），是实现复杂协议解析的神器。
