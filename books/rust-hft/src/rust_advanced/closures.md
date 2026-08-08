# 闭包、`Fn` Traits 与函数指针

闭包（closure）是可以捕获周围变量的匿名可调用值。它解决的实际问题是：一小段行为既需要像函数一样被传递，又需要随身带着上下文，例如“比较价格时带上当前阈值”。函数指针 `fn(A) -> B` 只表示某个普通函数入口，不携带捕获环境。

闭包怎样使用捕获环境，决定它实现 `FnOnce`、`FnMut` 还是 `Fn`；泛型、trait object 和函数指针则决定调用接口与分发方式。分发、分配、代码体积和可维护性是不同问题，不能用“哪一种永远最快”概括。

## 1. 闭包是什么，为什么需要它

普通函数不能直接捕获调用处的局部变量：

```rust
fn above(price: i64, threshold: i64) -> bool {
    price > threshold
}

fn main() {
    let threshold = 100;
    let is_above = |price: i64| price > threshold;

    assert!(above(101, threshold));
    assert!(is_above(101));
}
```

`is_above` 把“比较逻辑”和 `threshold` 的捕获方式组合成一个值。编译器会为每个闭包表达式生成一个匿名、具体类型；可以把它想成“保存捕获字段并实现调用 trait 的结构体”，但真实类型名和布局是实现细节，不应当作稳定 ABI（Application Binary Interface，二进制调用约定）。

闭包不必分配堆内存。局部闭包的环境可以直接放在拥有它的局部变量或结构体中；只有选择 `Box<dyn Fn...>` 等拥有型装箱时，才由 `Box` 引入堆分配。

## 2. `FnOnce`、`FnMut`、`Fn` 在约束什么

三个 trait 的核心区别是调用时怎样取得闭包环境：

| Trait | 调用接收者直觉 | 能做什么 | 典型场景 |
|---|---|---|---|
| `FnOnce` | 取得闭包本身 `self` | 可以把捕获值移出，因此至少能调用一次 | 一次性完成回调、交出资源 |
| `FnMut` | `&mut self` | 可以修改捕获状态，调用时需要独占访问 | 计数、累计、更新策略局部状态 |
| `Fn` | `&self` | 调用不需要可变访问或移出捕获值 | 只读判断、纯计算式回调 |

“至少能调用一次”很重要：所有闭包都实现 `FnOnce`，但只有会在调用中移出捕获值的闭包通常**只能**调用一次。实现 `Fn` 的闭包也能满足要求较弱的 `FnMut` 和 `FnOnce` 接口；实现 `FnMut` 的闭包也能作为 `FnOnce` 使用，反向不成立。

### 2.1 `FnOnce`：调用可能消耗捕获值

```rust
fn main() {
    let message = String::from("done");
    let finish = || drop(message);

    finish();
    // finish(); // 编译失败：第一次调用已经移出了 message。
}
```

这里不是 `move` 关键字本身决定“只能一次”，而是函数体把 `message` 交给了 `drop`。即便使用 `move` 捕获，只要调用时不把字段移出，闭包仍可能实现 `Fn` 或 `FnMut`。

### 2.2 `FnMut`：调用会更新环境

```rust
fn main() {
    let mut count = 0_u64;
    let mut observe = || count += 1;

    observe();
    observe();
    assert_eq!(count, 2);
}
```

调用需要对闭包环境的可变访问，所以绑定 `observe` 也要允许修改。它可以重复调用，但同一时刻不能通过安全引用并发地可变调用同一个闭包值。

### 2.3 `Fn`：调用只需要共享访问

```rust
fn main() {
    let threshold = 100_i64;
    let accepts = |price: i64| price <= threshold;

    assert!(accepts(99));
    assert!(accepts(100));
}
```

`Fn` 不等于“自动线程安全”。要把同一个闭包引用跨线程共享，闭包类型及其捕获内容还必须满足 [`Sync`](send_sync.md) 等线程边界；调用体依赖的外部资源也必须有正确同步。

## 3. 泛型、`dyn Fn` 和 `fn` 怎样选

`dyn Fn` 是一种 **trait object（特征对象）**：调用方只看见统一接口，运行时再通过一张分发表找到具体闭包的实现。因此它能统一不同的闭包类型，但通常比泛型少一些内联机会。

三种写法解决的约束不同：

| 表达方式 | 具体类型何时知道 | 堆分配 | 主要收益 | 主要代价 |
|---|---|---|---|---|
| `F: Fn(...)` | 编译期 | 不要求 | 静态分发，优化器容易看到目标 | 每种 `F` 可能产生实例，增加编译时间和代码体积 |
| `&dyn Fn(...)` | 运行期 | 不要求 | 借用异构回调，接口统一 | 间接调用，通常难以内联 |
| `Box<dyn Fn(...)>` | 运行期 | 通常一次 | 拥有大小不同的回调，可存入同一容器 | 堆分配、间接调用和动态生命周期 |
| `fn(...)` | 运行期保存函数入口 | 不要求 | 简单、可复制，适合 C ABI 或不捕获回调 | 不能捕获环境；通常也是间接调用 |

### 3.1 静态分发

```rust
struct Strategy<F> {
    on_tick: F,
}

impl<F> Strategy<F>
where
    F: Fn(i64) -> bool,
{
    fn decide(&self, price: i64) -> bool {
        (self.on_tick)(price)
    }
}

fn main() {
    let threshold = 100;
    let strategy = Strategy {
        on_tick: |price| price > threshold,
    };
    assert!(strategy.decide(101));
}
```

闭包环境直接成为 `Strategy<F>` 的字段，不要求单独分配。调用目标在编译期已知，为内联创造机会；“有机会”不等于保证完全内联，仍要看优化构建和生成代码。

### 3.2 动态分发

```rust
fn run(callback: &dyn Fn(i64) -> bool, price: i64) -> bool {
    callback(price)
}

fn main() {
    let threshold = 100;
    let callback = |price| price > threshold;
    assert!(run(&callback, 101));
}
```

`&dyn Fn` 证明动态分发本身不要求堆分配。控制面、插件边界或回调集合中，统一接口带来的简单性可能比一次间接调用更重要；若它位于已确认的逐消息热点，再比较泛型、枚举分发和动态分发的端到端结果。

## 4. 函数指针 `fn`

函数项和不捕获环境的闭包可以转换为函数指针：

```rust
fn add_one(value: i32) -> i32 {
    value + 1
}

fn apply(operation: fn(i32) -> i32, value: i32) -> i32 {
    operation(value)
}

fn main() {
    let named: fn(i32) -> i32 = add_one;
    let closure: fn(i32) -> i32 = |value| value + 1;

    assert_eq!(apply(named, 41), 42);
    assert_eq!(apply(closure, 41), 42);
}
```

捕获闭包不能转成普通 `fn`，因为一个函数地址没有地方保存捕获环境：

```rust,compile_fail
fn main() {
    let offset = 10;
    let _operation: fn(i32) -> i32 = |value| value + offset;
}
```

不要因为函数指针的值通常很小就断言它“极致优化”。函数指针调用通常是间接调用，可能阻止内联；泛型零捕获闭包甚至可能是零大小类型。函数指针更自然的理由通常是 ABI、统一的非捕获回调表示，或控制代码体积。

## 5. 判断闭包接口的步骤

遇到一个闭包，按下面顺序判断：

1. 捕获了什么，是按共享借用、可变借用还是移动？
2. 调用体会不会修改捕获值，或把它移出去？
3. 回调要调用一次还是多次，是否需要跨线程？
4. 具体类型能否在编译期确定，是否需要异构集合或插件？
5. 这条调用是不是已测量的热路径；动态调用、分配或代码膨胀哪个才是实际成本？

### Q1：`move` 闭包一定只实现 `FnOnce` 吗？

不一定。`move` 决定捕获时把值移进环境；闭包实现哪类调用 trait，还取决于调用体如何使用这些值。只读使用移入值的闭包仍可能实现 `Fn`。

### Q2：`Box<dyn Fn()>` 的两类主要成本是什么？

`Box` 通常带来一次拥有对象的堆分配，`dyn Fn` 带来动态分发；此外还要考虑生命周期和代码布局。若只是 `&dyn Fn()`，则没有 Box 的分配。

### Q3：为什么 `Fn` 不自动表示可并发调用？

`Fn` 只说明调用接收共享的 `&self`，不证明闭包值可以跨线程共享。跨线程还要满足 [`Send`/`Sync`](send_sync.md)，捕获的底层资源也要遵守并发协议。

## 小结

- 闭包是带捕获环境的匿名可调用值，函数指针只表示不带环境的函数入口；
- `FnOnce`、`FnMut`、`Fn` 描述调用如何取得和使用闭包环境；
- 泛型提供静态分发，trait object 提供运行时统一接口，两者都是权衡；
- `Box` 的分配成本和 `dyn` 的动态分发成本要分开说；
- 性能敏感路径不按口号选择“最快写法”，而是先定位瓶颈，再测分配、间接调用、代码体积和尾延迟。
