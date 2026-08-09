# 位运算与数值算法：先把边界说清，再追求简短

位运算经常让人产生一种错觉：代码只有一行，所以问题一定很简单。实际上，`1 << bit` 这一小段表达式里，就藏着整数提升、位宽、符号和移位范围等前提。数值算法也一样；公式写对了，不代表中间乘法不会先溢出。

本章先建立位宽、符号和移位范围的安全模型，再从定义推导标志位、异或抵消、子集枚举、最大公约数、安全最小公倍数和模快速幂。每种技巧都必须同时说明输入前提和中间值的溢出边界。

## 1. 位到底是什么

一个 `std::uint32_t` 可以看成 32 个从右到左编号的开关：

```text
位编号：  7 6 5 4 3 2 1 0
数值  ：  0 0 1 0 1 1 0 1
```

最低位编号为 0。若第 `k` 位为 1，这一位对数值的贡献是 `2^k`。

常用操作如下：

| 表达式 | 含义 |
|---|---|
| `a & b` | 两边对应位都为 1 时，结果位才为 1 |
| `a \| b` | 两边对应位至少一个为 1，结果位为 1 |
| `a ^ b` | 两边对应位不同时，结果位为 1 |
| `~a` | 每一位取反 |
| `a << k` | 向左移动 `k` 位 |
| `a >> k` | 向右移动 `k` 位 |

算法题里优先使用宽度明确的无符号类型，例如 `std::uint32_t` 或 `std::uint64_t`。这不是说“无符号永远更好”，而是位掩码本来就在描述一串位，无符号类型的算术和右移语义更适合这个模型。

## 2. 母题一：用一个整数保存 32 个布尔标志

### 2.1 白话题意

系统有 32 个开关，编号为 `0..31`。要求支持：

- 打开第 `bit` 个开关；
- 关闭第 `bit` 个开关；
- 查询它是否打开；
- 翻转它的状态。

先构造一个只有目标位为 1 的掩码：

```text
mask = 1 向左移动 bit 位
```

### 2.2 伪代码

```text
mask_for(bit):
    如果 bit 不在 [0, 32)：报告非法输入
    返回 1 << bit

set(bit):
    flags = flags OR mask_for(bit)

clear(bit):
    flags = flags AND (NOT mask_for(bit))

test(bit):
    返回 (flags AND mask_for(bit)) 不等于 0

toggle(bit):
    flags = flags XOR mask_for(bit)
```

### 2.3 为什么正确

`mask_for(bit)` 除目标位外全是 0：

- 与它做 OR 时，目标位一定变成 1，其他位与 0 做 OR 后保持原值；
- 与它的反码做 AND 时，目标位与 0 相与变成 0，其他位与 1 相与保持原值；
- 做 AND 后结果是否非零，恰好回答目标位是否为 1；
- 与 1 做 XOR 会翻转，与 0 做 XOR 会保持，因此只翻转目标位。

每个操作都只改变题目要求改变的那一位。

### 2.4 复杂度

固定宽度整数上的每次操作都是常数次机器整数运算：时间 `O(1)`，额外空间 `O(1)`。

### 2.5 完整 C++20 实现

```cpp
#include <cassert>
#include <cstdint>
#include <limits>
#include <stdexcept>

class BitFlags32 {
public:
    void set(unsigned bit) {
        bits_ |= mask_for(bit);
    }

    void clear(unsigned bit) {
        bits_ &= ~mask_for(bit);
    }

    [[nodiscard]] bool test(unsigned bit) const {
        return (bits_ & mask_for(bit)) != 0U;
    }

    void toggle(unsigned bit) {
        bits_ ^= mask_for(bit);
    }

    [[nodiscard]] std::uint32_t value() const noexcept {
        return bits_;
    }

private:
    static std::uint32_t mask_for(unsigned bit) {
        constexpr unsigned width = std::numeric_limits<std::uint32_t>::digits;
        if (bit >= width) {
            throw std::out_of_range{"bit index is outside uint32_t"};
        }
        return std::uint32_t{1} << bit;
    }

    std::uint32_t bits_{0};
};

int main() {
    BitFlags32 flags;
    assert(flags.value() == 0U);

    flags.set(0);
    flags.set(5);
    assert(flags.test(0));
    assert(flags.test(5));
    assert(!flags.test(4));
    assert(flags.value() == 33U);  // 2^5 + 2^0

    flags.clear(0);
    assert(!flags.test(0));
    assert(flags.test(5));

    flags.toggle(5);
    assert(!flags.test(5));
    flags.toggle(31);
    assert(flags.test(31));

    bool rejected = false;
    try {
        flags.set(32);
    } catch (const std::out_of_range&) {
        rejected = true;
    }
    assert(rejected);
}
```

### 2.6 测试时还要想什么

- 最低位 `0` 和最高合法位 `31`；
- 重复 `set` 或重复 `clear`，结果应保持稳定；
- 越界位 `32`，不能先移位再检查；
- 初始值是否明确为零。

## 3. 移位的四条安全规则

### 3.1 移位数量必须小于位宽

对 32 位值执行 `value << 32` 或 `value >> 32` 是未定义行为。运行机器可能“碰巧给出一个结果”，也不能依赖。

```cpp,ignore
if (bit >= std::numeric_limits<std::uint32_t>::digits) {
    // 先拒绝，再移位。
}
const std::uint32_t mask = std::uint32_t{1} << bit;
```

### 3.2 让左操作数先成为目标无符号类型

不要把 `1 << bit` 当成万能写法。字面量 `1` 的类型通常是 `int`，运算可能先在有符号 `int` 中发生。

```cpp,ignore
const std::uint64_t mask = std::uint64_t{1} << bit;
```

### 3.3 不要对负数做左移

有符号负数左移属于未定义行为。有符号正数左移也有可表示范围等额外条件。描述位模式时，先把输入域定义成无符号值，通常更容易推理。

### 3.4 小整数可能先发生整数提升

`std::uint8_t` 参与 `~`、`<<` 等运算时，通常会先提升为 `int`。若你只想保留 8 位，需要在理解运算结果后显式转换；更简单的算法代码通常直接在 `uint32_t` 或 `uint64_t` 上操作。

## 4. 母题二：成对元素中找唯一值，并统计它的 1 位

### 4.1 白话题意

给定一组 32 位无符号整数。题目保证：除一个数只出现一次外，其余每个数都恰好出现两次。找出唯一值，并统计它的二进制表示中有多少个 1。

关键性质是：

```text
x XOR x = 0
x XOR 0 = x
```

XOR 还满足交换律和结合律，所以成对元素无论出现在什么位置，最终都会互相抵消。

### 4.2 伪代码

```text
answer = 0
依次读取每个 value：
    answer = answer XOR value

ones = answer 中值为 1 的位数
返回 (answer, ones)
```

### 4.3 为什么正确

把全部 XOR 按相同数值重新分组不会改变结果。每个出现两次的值产生 `x XOR x = 0`，所有这些零继续 XOR 仍是零；唯一值只出现一次，最后得到 `0 XOR unique = unique`。

`std::popcount` 按定义返回无符号整数二进制表示中 1 的数量，因此第二个结果也正确。

注意：正确性依赖“恰好一个值出现一次，其余值恰好两次”的输入保证。若数据不满足前提，XOR 仍会返回一个数，但那个数不一定有题目想要的含义。

### 4.4 复杂度

扫描 `n` 个元素，时间 `O(n)`；只保存一个累计值，额外空间 `O(1)`。固定 32 位上的 `popcount` 在该模型中视为 `O(1)`。

### 4.5 完整 C++20 实现

```cpp
#include <bit>
#include <cassert>
#include <cstdint>
#include <utility>
#include <vector>

[[nodiscard]] std::pair<std::uint32_t, int> unique_value_and_popcount(
    const std::vector<std::uint32_t>& values) {
    std::uint32_t unique{0};
    for (const std::uint32_t value : values) {
        unique ^= value;
    }
    return {unique, std::popcount(unique)};
}

int main() {
    assert((unique_value_and_popcount({4, 1, 4, 7, 1}) ==
            std::pair<std::uint32_t, int>{7, 3}));
    assert((unique_value_and_popcount({0}) ==
            std::pair<std::uint32_t, int>{0, 0}));
    assert((unique_value_and_popcount({9, 12, 9}) ==
            std::pair<std::uint32_t, int>{12, 2}));

    const std::uint32_t high_bit = std::uint32_t{1} << 31;
    assert((unique_value_and_popcount({5, high_bit, 5}) ==
            std::pair<std::uint32_t, int>{high_bit, 1}));
}
```

### 4.6 常见追问

- 若有两个数各出现一次，其他数出现两次，可以先 XOR 得到二者之差异，再用其中一个为 1 的位把输入分组；
- 若其余数出现三次，简单 XOR 不再抵消，需要逐位计数并对 3 取模；
- 若题目没有次数保证，应使用哈希计数或先验证输入，不能套用这段代码。

## 5. 进阶：用位掩码枚举一个小集合的全部子集

### 5.1 白话题意

给定 `n` 个元素，返回它的全部子集。这里限定 `n <= 20`，因为答案本身就有 `2^n` 个；即使每个子集只占一个字节，`n` 很大时也无法完整输出。

把一个从 `0` 到 `2^n - 1` 的整数看成选择方案：第 `i` 位为 1 表示选择第 `i` 个元素，为 0 表示不选。

### 5.2 伪代码

```text
如果 n 大于允许上限：报告输入过大
limit = 1 << n
answer = 空列表

对于 mask 从 0 到 limit - 1：
    subset = 空列表
    对于 i 从 0 到 n - 1：
        如果 mask 的第 i 位为 1：
            把 values[i] 加入 subset
    把 subset 加入 answer

返回 answer
```

### 5.3 为什么正确

任意子集都能唯一对应一个 `n` 位掩码：包含第 `i` 个元素就把第 `i` 位设为 1，否则设为 0。反过来，每个掩码也唯一决定一个子集。因此遍历 `[0, 2^n)` 的每个掩码，既不会漏掉子集，也不会重复产生同一个选择方案。

### 5.4 复杂度

共有 `2^n` 个掩码，每个掩码检查 `n` 位，时间 `O(n 2^n)`。返回内容本身最坏也包含 `n 2^(n-1)` 个元素，因此不能声称空间很小。算法循环使用的临时状态较少，但输出空间为 `O(n 2^n)`。

### 5.5 完整 C++20 实现

```cpp
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <utility>
#include <vector>

[[nodiscard]] std::vector<std::vector<int>> all_subsets(
    const std::vector<int>& values) {
    constexpr std::size_t maximum_elements = 20;
    if (values.size() > maximum_elements) {
        throw std::invalid_argument{"too many subsets to materialize"};
    }

    const std::uint64_t limit = std::uint64_t{1} << values.size();
    std::vector<std::vector<int>> answer;
    answer.reserve(static_cast<std::size_t>(limit));

    for (std::uint64_t mask = 0; mask < limit; ++mask) {
        std::vector<int> subset;
        for (std::size_t i = 0; i < values.size(); ++i) {
            if ((mask & (std::uint64_t{1} << i)) != 0U) {
                subset.push_back(values[i]);
            }
        }
        answer.push_back(std::move(subset));
    }
    return answer;
}

int main() {
    const auto empty = all_subsets({});
    assert(empty.size() == 1);
    assert(empty[0].empty());

    const auto subsets = all_subsets({10, 20, 30});
    assert(subsets.size() == 8);
    assert(subsets[0].empty());
    assert((subsets[1] == std::vector<int>{10}));
    assert((subsets[2] == std::vector<int>{20}));
    assert((subsets[3] == std::vector<int>{10, 20}));
    assert((subsets[7] == std::vector<int>{10, 20, 30}));

    bool rejected = false;
    try {
        static_cast<void>(all_subsets(std::vector<int>(21, 0)));
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);
}
```

### 5.6 测试时还要想什么

- 空集合有一个子集：空集，而不是零个子集；
- 输入元素值相同但位置不同，按“位置选择”会产生看起来相同的子集；若题目要求值去重，需要先定义输出语义；
- `1 << n` 之前必须保证移位合法；本例更早使用 `n <= 20` 限制了输出规模；
- 只要求计数时，不要真的构造全部答案。

## 6. 最大公约数与不会静默溢出的最小公倍数

### 6.1 白话题意

给定两个非负 64 位整数 `a`、`b`：

- 求最大公约数 `gcd(a, b)`；
- 求最小公倍数 `lcm(a, b)`；若结果无法用 `uint64_t` 表示，返回“没有可表示结果”。

本章规定 `gcd(0, 0) = 0`，并规定任一输入为零时 `lcm = 0`。

欧几里得算法使用下面的事实：

```text
gcd(a, b) = gcd(b, a mod b)
```

### 6.2 伪代码

```text
gcd(a, b):
    当 b 不等于 0：
        remainder = a mod b
        a = b
        b = remainder
    返回 a

checked_lcm(a, b):
    如果 a == 0 或 b == 0：返回 0
    g = gcd(a, b)
    reduced = a / g
    如果 reduced > UINT64_MAX / b：返回“溢出”
    返回 reduced * b
```

### 6.3 为什么正确

若 `a = q*b + r`，一个数同时整除 `a` 和 `b`，当且仅当它同时整除 `b` 和 `r`，所以把 `(a, b)` 换成 `(b, a mod b)` 不改变公约数集合。余数严格小于 `b`，过程最终会在余数为零时停止；此时留下的非零数就是最大公约数。

对非零输入有：

```text
lcm(a, b) = (a / gcd(a, b)) * b
```

先做除法，既保持数学结果，又比先算 `a*b` 更不容易溢出。乘法前的除法比较准确判断最终乘积是否超过 `UINT64_MAX`。

### 6.4 复杂度

欧几里得算法时间为 `O(log min(a, b))`，额外空间 `O(1)`。安全 `lcm` 只在其后增加常数次整数运算。

### 6.5 完整 C++20 实现

```cpp
#include <cassert>
#include <cstdint>
#include <limits>
#include <optional>

[[nodiscard]] std::uint64_t gcd_u64(std::uint64_t a,
                                    std::uint64_t b) noexcept {
    while (b != 0U) {
        const std::uint64_t remainder = a % b;
        a = b;
        b = remainder;
    }
    return a;
}

[[nodiscard]] std::optional<std::uint64_t> checked_lcm_u64(
    std::uint64_t a,
    std::uint64_t b) noexcept {
    if (a == 0U || b == 0U) {
        return std::uint64_t{0};
    }

    const std::uint64_t divisor = gcd_u64(a, b);
    const std::uint64_t reduced = a / divisor;
    const std::uint64_t maximum =
        std::numeric_limits<std::uint64_t>::max();
    if (reduced > maximum / b) {
        return std::nullopt;
    }
    return reduced * b;
}

int main() {
    assert(gcd_u64(48, 18) == 6);
    assert(gcd_u64(0, 7) == 7);
    assert(gcd_u64(0, 0) == 0);

    assert(checked_lcm_u64(12, 18) == 36);
    assert(checked_lcm_u64(0, 99) == 0);

    const std::uint64_t maximum =
        std::numeric_limits<std::uint64_t>::max();
    assert(checked_lcm_u64(maximum, 1) == maximum);
    assert(!checked_lcm_u64(maximum, 2).has_value());
}
```

### 6.6 有符号输入为什么要另外处理

数学上的 `gcd(-a, b)` 通常使用绝对值。但最小的 64 位有符号整数没有对应的正 `int64_t` 值，直接对它调用普通取负或 `abs` 可能溢出。一个清楚的接口应选择以下办法之一：

- 题目本来就只接受非负数，像本例一样使用 `uint64_t`；
- 写一个经过证明的“有符号值转无符号幅度”函数；
- 使用更宽的整数表示，并明确平台依赖。

不要在没有检查输入域时先写 `abs(a)`。

## 7. 进阶：不会在模乘中先溢出的快速幂

### 7.1 白话题意

计算：

```text
base^exponent mod modulus
```

输入都是 64 位无符号整数，`modulus == 0` 视为非法。普通快速幂把指数按二进制拆开，只需 `O(log exponent)` 次平方或相乘；但若直接写 `a * b % modulus`，乘法可能在取模之前就溢出。

本例先给一个完全使用标准 `uint64_t` 的便携版本：用“加倍并取模”实现安全模乘。它不是所有平台上最快的版本，却把正确性边界写得很清楚。

### 7.2 伪代码

```text
add_mod(a, b, m):          // 前提：a < m，b < m，m > 0
    如果 a >= m - b：
        返回 a - (m - b)   // 与 a+b-m 同余，但没有先做溢出加法
    返回 a + b

multiply_mod(a, b, m):
    如果 m == 0：报告参数非法
    a = a mod m
    b = b mod m
    result = 0
    当 b > 0：
        如果 b 的最低位为 1：result = add_mod(result, a, m)
        a = add_mod(a, a, m)
        b 向右移动一位
    返回 result

power_mod(base, exponent, m):
    如果 m == 0：返回非法
    result = 1 mod m
    base = base mod m
    当 exponent > 0：
        如果 exponent 的最低位为 1：
            result = multiply_mod(result, base, m)
        base = multiply_mod(base, base, m)
        exponent 向右移动一位
    返回 result
```

### 7.3 为什么正确

`add_mod` 的两个分支分别处理 `a+b < m` 与 `a+b >= m`。第二个分支计算与 `a+b-m` 相等的 `a-(m-b)`，避免真的形成可能溢出的 `a+b`。

模乘循环维护：

> `result + a * remaining_b` 与原始乘积在模 `m` 下同余。

若最低位为 1，就把当前 `a` 加入结果；随后 `a` 加倍、`remaining_b` 减半，正好处理二进制乘法的下一位。循环结束时剩余乘数为零，所以 `result` 是乘积的模。

快速幂循环维护：

> `result * base^remaining_exponent` 与原始 `base^exponent` 在模 `m` 下同余。

指数最低位为 1 时把当前底数乘入结果；无论最低位是什么，底数平方、指数减半都保持这个等式。指数归零时，`result` 就是答案。

### 7.4 复杂度

快速幂有 `O(log exponent)` 轮。便携模乘每次检查乘数的二进制位，最多 64 轮；若把整数位宽也作为变量，可写成 `O(log exponent * log modulus)`，在固定 64 位机器模型中则是每轮至多 64 次简单操作。额外空间 `O(1)`。

### 7.5 完整 C++20 实现

```cpp
#include <cassert>
#include <cstdint>
#include <limits>
#include <optional>
#include <stdexcept>

[[nodiscard]] std::uint64_t add_mod(std::uint64_t a,
                                    std::uint64_t b,
                                    std::uint64_t modulus) noexcept {
    // 调用者保证 a < modulus、b < modulus、modulus > 0。
    if (a >= modulus - b) {
        return a - (modulus - b);
    }
    return a + b;
}

[[nodiscard]] std::uint64_t multiply_mod(std::uint64_t a,
                                         std::uint64_t b,
                                         std::uint64_t modulus) {
    if (modulus == 0U) {
        throw std::invalid_argument{"modulus must be nonzero"};
    }
    a %= modulus;
    b %= modulus;
    std::uint64_t result{0};

    while (b != 0U) {
        if ((b & std::uint64_t{1}) != 0U) {
            result = add_mod(result, a, modulus);
        }
        a = add_mod(a, a, modulus);
        b >>= 1U;
    }
    return result;
}

[[nodiscard]] std::optional<std::uint64_t> power_mod(
    std::uint64_t base,
    std::uint64_t exponent,
    std::uint64_t modulus) noexcept {
    if (modulus == 0U) {
        return std::nullopt;
    }

    std::uint64_t result = std::uint64_t{1} % modulus;
    base %= modulus;
    while (exponent != 0U) {
        if ((exponent & std::uint64_t{1}) != 0U) {
            result = multiply_mod(result, base, modulus);
        }
        base = multiply_mod(base, base, modulus);
        exponent >>= 1U;
    }
    return result;
}

int main() {
    assert(power_mod(2, 10, 1000) == 24);
    assert(power_mod(5, 0, 7) == 1);
    assert(power_mod(123, 456, 1) == 0);
    assert(!power_mod(2, 10, 0).has_value());

    bool rejected_zero_modulus = false;
    try {
        static_cast<void>(multiply_mod(2, 10, 0));
    } catch (const std::invalid_argument&) {
        rejected_zero_modulus = true;
    }
    assert(rejected_zero_modulus);

    const std::uint64_t maximum =
        std::numeric_limits<std::uint64_t>::max();
    // (m - 1)^2 mod m == 1；中间平方不能放入 uint64_t。
    assert(power_mod(maximum - 1, 2, maximum) == 1);
}
```

### 7.6 工程与面试追问

- 某些编译器提供 `unsigned __int128`，可以让 64 位模乘更短、更快，但它不是标准 C++20 类型；使用前要确认平台；
- 对固定奇数模数和大量运算，可研究 Montgomery reduction，但它属于进阶优化；
- 密码学代码还要考虑常数时间、侧信道和经过审计的库，不能把教学快速幂直接当生产密码实现；
- `0^0` 的数学语境可能有不同约定。本例按算法常用的空乘积约定返回 `1 mod modulus`，接口文档必须说明。

## 8. 章末做题方法：写出位宽和数值域

1. **读题定类型**：明确有符号/无符号、位宽、是否允许负数、乘法中间值是否可能溢出；位掩码先画最低几位。
2. **把操作翻成集合**：置位是加入，清位是删除，测试位是成员判断，异或是奇偶抵消；再选择 `|`、`&`、`^` 和移位。
3. **逐位推演**：对一个小二进制数手算每一步，子集枚举记录 `mask` 对应元素，欧几里得算法记录 `(a,b)→(b,a%b)`。
4. **验算边界**：0、最高位、全 1、相等数、互质数与最大输入；快速幂检查指数 0，LCM 先除后乘。

常见陷阱：移位位数达到类型宽度；负数右移和溢出依赖实现/产生未定义行为；`1 << k` 的 `1` 类型过窄；用浮点 `pow` 求整数幂；`a*b/gcd` 先溢出。

## 9. 一张提交前检查表

位操作检查：

- [ ] 位掩码是否使用了宽度明确的无符号类型？
- [ ] 移位数量是否先检查为小于位宽？
- [ ] 是否误把 `1 << bit` 留在有符号 `int` 中计算？

数值运算检查：

- [ ] 输入前提（成对出现、值域、非负、模数非零）是否明确？
- [ ] `2^n` 个答案是否会在构造前就耗尽时间或内存？
- [ ] `a*b % m` 是否可能在取模前溢出？
- [ ] `a*b/gcd` 是否应该改成先除后乘并检查？
- [ ] 对最小有符号整数取绝对值是否安全？

## 10. 变体练习

1. 给定两个只出现一次的值、其余值出现两次，返回这两个值并证明分组不会把它们放到同一组。

<details><summary>参考答案</summary>

全体异或得 `x=a xor b`，成对值抵消。取最低置位 `low=x & (~x+1)`；因为该位在 x 中为 1，a、b 在此位必一 0 一 1。按 `value & low` 是否为 0 分组并分别异或，重复对仍进同组抵消，最后得到 a、b。时间 `O(n)`、空间 `O(1)`；若不满足“恰有两个单独值”，语义不成立。

</details>

2. 用 `mask & (mask - 1)` 每次清除最低的 1，手写一个 `popcount`，并与 `std::popcount` 随机对拍。

<details><summary>参考答案</summary>

```cpp,ignore
unsigned popcount_u64(std::uint64_t x) {
    unsigned count = 0;
    while (x != 0) { x &= x - 1; ++count; }
    return count;
}
```

`x-1` 把最低 1 变 0 并把其右侧 0 变 1，与原数相与只清掉该最低 1；循环次数等于置位数，最坏 `O(64)=O(1)`。对 0、全 1、单 bit、随机 `uint64_t` 与 `std::popcount` 比较，包含最高位以避免有符号移位错误。

</details>

3. 只枚举某个掩码的所有非空子掩码；解释为什么循环会终止。

<details><summary>参考答案</summary>

```cpp,ignore
for (std::uint64_t sub = mask; sub != 0; sub = (sub - 1) & mask) {
    // 使用 sub
}
```

`sub-1` 找到数值更小的位形，再与 mask 保证不出现 mask 之外的 1；每轮 `sub` 严格减小，有限次后到 0，因此终止。共有 `2^popcount(mask)-1` 个非空子掩码；若还需空集，要在循环后单独处理 0。

</details>

4. 计算 `base^exponent`，若完整结果超出 `uint64_t` 就返回空；不要借助浮点数猜测。

<details><summary>参考答案</summary>

用二进制快速幂。每次乘法前检查 `a!=0 && b>UINT64_MAX/a`；指数当前位为 1 才把 result 乘 base，指数右移后如仍需继续再安全地平方 base。循环不变量是 `result × base^remaining` 等于原目标（在数学整数中）。时间 `O(log exponent)`、空间 `O(1)`；`exponent=0` 返回 1，包括 `0^0` 要按接口约定声明。

</details>

5. 把 `checked_lcm_u64` 扩展到一组非负整数；中途出现溢出就停止。

<details><summary>参考答案</summary>

从 `answer=1` 依次折叠；对 x，若 `answer==0 || x==0` 则新答案为 0，否则先算 `g=gcd(answer,x)`，令 `q=answer/g`，检查 `x>UINT64_MAX/q` 时返回空，否则 `answer=q*x`。先除后乘降低中间溢出风险。不变量是 answer 为已处理前缀的 LCM；空集合是否返回 1 要在接口中声明。总时间取决于各次 gcd，额外空间 `O(1)`。

</details>

学位运算时，真正重要的不是把代码压缩到最短，而是能说出：每一位代表什么、输入前提是什么、哪个中间值可能越界。做到这一点后，那些看似神奇的一行技巧，大多都可以从定义重新推导出来。
