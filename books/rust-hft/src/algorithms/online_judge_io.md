# 在线笔试输入输出：把“会写函数”变成“能通过 OJ”

很多人第一次参加在线笔试时，算法明明想对了，却卡在输入输出：第一行的 `T` 是什么、为什么 `getline` 读到空串、函数题的代码为什么不能直接提交、结果后面能不能多打印一句提示。

`OJ` 是 Online Judge（在线判题系统）：平台编译并运行程序，用隐藏输入检查输出；`ACM 模式`通常指你要自己编写 `main`、读取标准输入并打印标准输出，而不是只填写一个函数。不同平台叫法可能不同，最终以题面给出的模板为准。

这些问题不属于算法本身，却会直接决定答案能不能被判题机接受。本章从一个最小程序开始，依次讲清单组输入、多组输入、读到文件结束、整行文本、函数题与完整程序的转换。

本章示例都使用 C++20。每个完整程序在没有标准输入时都会直接返回 `0`，不会等待额外输入，也不会输出测试文字。

## 1. OJ 到底怎样运行你的程序

在线判题系统通常会做三件事：

1. 用指定编译器和语言标准编译你的源文件；
2. 把测试数据放进程序的标准输入 `stdin`；
3. 把程序的标准输出 `stdout` 与标准答案比较。

你在本地手动输入的内容，对 OJ 来说只是一个提前准备好的文本文件。例如题面写：

```text
输入：
5
3 1 4 1 5

输出：
14
```

程序看到的是一串由空白分隔的字符。`operator>>` 默认把空格、换行和制表符都当成分隔符，因此下面两份输入对逐个读取整数的程序没有区别：

```text
5
3 1 4 1 5
```

```text
5 3
1 4
1 5
```

只有题目把空格也当作数据的一部分时，才需要按整行读取。

## 2. 提交前先确认五件事

不要只看样例猜输入格式。先在题面中找到：

1. **是一组数据，还是多组数据？**
2. **多组数据由第一行 `T` 指定，还是一直读到 EOF？**
3. **每组数据的边界怎样确定？** 是固定字段、先给长度，还是一整行？
4. **输出是否要求 `Case #1:`、空格、精度或空行？**
5. **编译标准是 C++17、C++20，还是平台自定义版本？**

常见形式可以先记成下表：

| 题面描述 | 主循环形状 |
|---|---|
| “输入一个数组……” | 只调用一次 `solve_one_case()` |
| “第一行是测试组数 `T`” | 读取 `T`，循环恰好 `T` 次 |
| “有多组输入，直到文件结束” | 读取每组第一个字段，成功就继续 |
| “接下来有 `n` 行字符串” | 读完 `n` 后切换到 `getline` |
| 平台只让填写一个函数 | 不自己读取输入；遵守平台给出的函数签名 |

“多组输入”并不自动表示有 `T`。这两种格式写错，样例可能碰巧通过，隐藏测试却会整体错位。

## 3. 最小程序与快 I/O

算法题常用下面两行设置：

```cpp,ignore
std::ios::sync_with_stdio(false);
std::cin.tie(nullptr);
```

- 第一行允许 C++ iostream 不再与 C 的 `stdio` 保持同步，通常能减少开销；
- 第二行解除 `cin` 与 `cout` 的自动绑定，读取前不再强制刷新输出缓冲。

要在任何输入输出发生**之前**设置它们。关闭同步后，不要再随意混用 `cin/cout` 与 `scanf/printf`，否则缓冲顺序容易变得难以推理。

`'\n'` 只写入换行；`std::endl` 还会立刻刷新缓冲。普通批量输出一般使用 `'\n'`，只有交互题或确实需要立即发送内容时才主动刷新。

## 4. 母题一：单组输入

### 4.1 白话题意

第一行给非负整数 `n`，接下来给 `n` 个 64 位整数。题目保证总和可以放进 `long long`，输出总和。

```text
输入：
5
3 1 4 1 5

输出：
14
```

### 4.2 伪代码

```text
读取 n
如果连 n 都没有读到：正常结束

sum = 0
重复 n 次：
    读取 value
    如果数据提前结束：报告输入失败
    sum += value

输出 sum 和换行
```

### 4.3 为什么正确

循环开始第 `i` 次读取前，`sum` 等于已经读取的前 `i` 个数之和。读入下一个数并加到 `sum` 后，不变量对 `i+1` 继续成立。循环结束时恰好处理了 `n` 个数，所以输出就是题目要求的总和。

### 4.4 复杂度

- 时间：`O(n)`；
- 除输入本身外的额外空间：`O(1)`。

### 4.5 完整 C++20

```cpp
#include <cstddef>
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::size_t count{};
    if (!(std::cin >> count)) {
        return std::cin.eof() ? 0 : 1; // 空输入正常；非法首字段失败
    }

    long long sum{0};
    for (std::size_t i = 0; i < count; ++i) {
        long long value{};
        if (!(std::cin >> value)) {
            return 1; // 题目承诺有 n 个数；缺少数据说明输入不完整
        }
        sum += value;
    }

    std::cout << sum << '\n';
}
```

这里不需要先把所有数放进 `vector`，因为求和只依赖当前数和累计值。若算法需要排序、回看或随机访问，再保存完整数组。

### 4.6 测试

至少手动覆盖：

```text
n = 0                  -> 0
n = 1, values = [-7]   -> -7
正负数抵消             -> 检查没有把初始值写错
输入在同一行           -> 应与分行输入相同
```

真实题目若没有保证总和落在 64 位范围内，还要根据约束使用更宽类型或显式检查溢出。更换输入输出模板不会自动解决数值正确性。

## 5. 母题二：第一行给测试组数 `T`

### 5.1 白话题意

第一行给测试组数 `T`。每组先给长度 `n`，再给 `n` 个整数，输出本组最大值；`n == 0` 时输出 `EMPTY`。题目明确要求格式为 `Case #x: answer`，编号从 1 开始。

```text
输入：
3
4 7 2 9 1
1 -5
0

输出：
Case #1: 9
Case #2: -5
Case #3: EMPTY
```

### 5.2 伪代码

```text
读取 T
如果没有任何输入：正常结束

for case_id 从 1 到 T：
    读取 n
    如果 n == 0：输出本组 EMPTY，继续

    读取第一个数作为 best
    再读取 n-1 个数：best = max(best, value)
    按题目格式输出本组答案
```

### 5.3 为什么正确

外层循环恰好处理题面声明的 `T` 组，不会把下一组的开头误当成本组数据。对非空组，`best` 始终是本组已经读取元素的最大值；读完 `n` 个元素后，它就是整组最大值。空组由题目单独定义为 `EMPTY`。

### 5.4 复杂度

若全部测试组共有 `N` 个元素，总时间为 `O(N+T)`，额外空间为 `O(1)`。

### 5.5 完整 C++20

```cpp
#include <algorithm>
#include <cstddef>
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int test_count{};
    if (!(std::cin >> test_count)) {
        return std::cin.eof() ? 0 : 1;
    }
    if (test_count < 0) {
        return 1;
    }

    const std::size_t total_cases = static_cast<std::size_t>(test_count);
    for (std::size_t case_index = 0; case_index < total_cases; ++case_index) {
        const std::size_t case_id = case_index + 1;
        std::size_t count{};
        if (!(std::cin >> count)) {
            return 1;
        }

        if (count == 0) {
            std::cout << "Case #" << case_id << ": EMPTY\n";
            continue;
        }

        long long best{};
        if (!(std::cin >> best)) {
            return 1;
        }
        for (std::size_t i = 1; i < count; ++i) {
            long long value{};
            if (!(std::cin >> value)) {
                return 1;
            }
            best = std::max(best, value);
        }
        std::cout << "Case #" << case_id << ": " << best << '\n';
    }
}
```

循环内部用从 0 开始的 `case_index < total_cases`，只在输出时计算 `case_index + 1`。若直接写有符号整数的 `case_id <= test_count`，当 `T == INT_MAX` 时，最后一轮结束后的自增会溢出。

不要擅自打印 `Case #x:`。只有题目明确要求时才能加入；判题系统通常不会因为“更友好”而忽略额外文字。

### 5.6 测试

- `T = 0`；
- 某组 `n = 0`；
- 只有一个负数，避免把最大值错误初始化为零；
- 多组数据写在同一行；
- 最后一组缺少元素时应以非零状态退出，而不是使用未读取的值。

## 6. 母题三：一直读取到 EOF

### 6.1 EOF 是什么

EOF 是 end of file，即输入文件结束。题面若说“每行两个整数，多组输入直到文件结束”，就没有 `T`，也不能凭空先读一组数量。

最短写法常见为：

```cpp,ignore
long long left, right;
while (std::cin >> left >> right) {
    std::cout << left + right << '\n';
}
```

它适合 OJ 保证输入完整的情况。为了把“正常 EOF”和“半组数据”区分开，下面写成更明确的版本。

### 6.2 伪代码

```text
无限循环：
    尝试读取本组第一个数 a
    如果因为 EOF 没读到：正常结束
    如果因为非法字符没读到：输入失败

    读取本组第二个数 b
    如果没读到：输入失败
    输出 a + b
```

### 6.3 正确性与复杂度

每次成功进入输出步骤时，程序恰好读到一对完整的 `(a,b)`，所以不会跨组错位。正常 EOF 只会结束循环。处理 `P` 对输入的时间为 `O(P)`，额外空间为 `O(1)`。

### 6.4 完整 C++20

题目在本例中保证每对数之和可由 `long long` 表示。

```cpp
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    while (true) {
        long long left{};
        if (!(std::cin >> left)) {
            return std::cin.eof() ? 0 : 1;
        }

        long long right{};
        if (!(std::cin >> right)) {
            return 1; // 已有半组数据，不能把它当成一组完整答案
        }
        std::cout << left + right << '\n';
    }
}
```

### 6.5 测试

```text
输入为空                    -> 无输出，返回 0
1 2                         -> 3
1 2\n3 4                   -> 3\n7
只有一个末尾数字            -> 返回非零，不输出不完整组
中间出现非数字文本          -> 返回非零
```

在终端里交互运行时，程序会继续等待，因为你还没有发送 EOF。这不是死循环。在 macOS/Linux 终端通常可按 `Ctrl-D` 表示输入结束；Windows 控制台常用 `Ctrl-Z` 后回车。

## 7. 母题四：`>>` 与 `getline` 混用

### 7.1 为什么会读到空行

`std::cin >> line_count` 会读取数字，但通常把数字后面的换行符留在输入缓冲中。紧接着调用 `getline` 时，它看到的第一个字符就是换行，于是返回一个空字符串。

若题目说“接下来恰好有 `n` 行文本，而且空行也是合法数据”，正确做法是在第一次 `getline` 前只丢掉上一行剩余内容：

```cpp,ignore
std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
```

不要机械地使用 `std::getline(std::cin >> std::ws, line)`。`std::ws` 会跳过所有前导空白，也会吞掉本来有意义的空行和行首空格。

### 7.2 白话题意

第一行给 `n`，接下来恰好有 `n` 行任意文本，空行和行首空格都算内容。输出每行的编号、字节长度和原文。

### 7.3 伪代码

```text
用 >> 读取 n
丢弃 n 所在行剩余内容，直到换行

重复 n 次：
    用 getline 读取完整一行
    如果读取失败：返回输入错误
    若末尾残留 CR：去掉 CR
    输出 行号、字节长度、原文
```

这里的长度是 `std::string::size()` 返回的字节数，不是通用 Unicode 字符数量。

### 7.4 为什么正确

第一次 `ignore` 只跨过数字所在行的剩余字符。之后每次 `getline` 恰好消费一行，包括可能为空的行；循环执行 `n` 次，所以输入行与输出行一一对应，行内空格不会被拆开。

### 7.5 复杂度

设所有文本共有 `L` 个字节，时间为 `O(L+n)`；除当前行外额外空间为 `O(1)`，当前字符串最多占最长一行的空间。

### 7.6 完整 C++20

```cpp
#include <cstddef>
#include <iostream>
#include <limits>
#include <string>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::size_t line_count{};
    if (!(std::cin >> line_count)) {
        return std::cin.eof() ? 0 : 1;
    }
    std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');

    for (std::size_t index = 0; index < line_count; ++index) {
        std::string line;
        if (!std::getline(std::cin, line)) {
            return 1;
        }
        if (!line.empty() && line.back() == '\r') {
            line.pop_back(); // 兼容可能残留的 CRLF 行尾
        }
        std::cout << (index + 1) << ' ' << line.size() << ' ' << line << '\n';
    }
}
```

### 7.7 测试

输入中至少放入：普通单词、含多个空格的句子、真正的空行、以空格开头的行，以及最后一行没有额外空行的情况。

## 8. 母题五：把“只填函数”转换成完整程序

有的平台提供节点类型和调用代码，只要求填写：

```cpp,ignore
std::size_t first_not_less(const std::vector<long long>& values,
                           long long target) {
    // 只填写这里；不要自己写 main 或读取 cin。
}
```

这种题由平台负责输入输出。若你要在 ACM 模式中使用同一算法，应把算法函数保留，再写一层很薄的 `main`：

```text
main 负责：读取 -> 调用 -> 输出
算法函数负责：只根据参数计算并返回答案
```

不要把 `cin` 和 `cout` 塞进算法函数。分层以后，函数可以直接单元测试，也更容易在两种判题模式之间切换。

### 8.1 题意与伪代码

输入有序数组长度 `n`、目标值 `target`，再输入 `n` 个数。返回第一个不小于目标的下标；全部较小时返回 `n`。

```text
left = 0, right = n
while left < right:
    mid = left + (right-left)/2
    if values[mid] < target: left = mid+1
    else: right = mid
return left
```

不变量是 `[0,left)` 全部小于目标，`[right,n)` 全部不小于目标。循环结束时两端相等，正好位于两段的边界，因此答案正确。时间 `O(log n)`，算法额外空间 `O(1)`；读取并保存输入需要 `O(n)` 空间。

### 8.2 完整 C++20

```cpp
#include <cstddef>
#include <iostream>
#include <vector>

std::size_t first_not_less(const std::vector<long long>& values,
                           long long target) {
    std::size_t left = 0;
    std::size_t right = values.size();
    while (left < right) {
        const std::size_t mid = left + (right - left) / 2;
        if (values[mid] < target) {
            left = mid + 1;
        } else {
            right = mid;
        }
    }
    return left;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::size_t count{};
    if (!(std::cin >> count)) {
        return std::cin.eof() ? 0 : 1;
    }
    long long target{};
    if (!(std::cin >> target)) {
        return 1;
    }

    std::vector<long long> values(count);
    for (long long& value : values) {
        if (!(std::cin >> value)) {
            return 1;
        }
    }

    std::cout << first_not_less(values, target) << '\n';
}
```

题面保证输入非递减时，算法函数不必每次重新检查排序；若输入不可信，则应在接口层验证并定义错误语义。

## 9. 输出格式：多一个字符也可能错

OJ 常见输出要求包括：

- 每个答案一行；
- 同一行字段用一个空格分隔，行尾不要多余空格；
- 固定小数位数；
- 按指定顺序输出；
- 没有答案时输出特定文字或数字；
- 每组前加题目指定的编号。

固定小数位数可写：

```cpp,ignore
#include <iomanip>
std::cout << std::fixed << std::setprecision(6) << answer << '\n';
```

这表示输出小数点后六位，不表示计算本身变得更精确。中间计算仍应选择合适的类型，并按题目定义处理舍入误差。

调试文字不要写到标准输出：

```cpp,ignore
std::cout << "reading case..."; // 提交前必须删除
```

本地调试可以使用调试器，或临时写到 `std::cerr`，但最终提交最好删掉无关输出。不要依赖某个平台“一定忽略 stderr”。

大量小片段输出时，可以先写入字符串缓冲，或至少避免每行 `std::endl` 强制刷新。是否真的需要优化，应结合输入规模，而不是一开始写复杂缓冲器。

## 10. C++17 与 C++20：代码能在本地编译，不等于 OJ 能编译

提交页面通常允许选择语言版本。若选择 GNU++17，就不能假设 C++20 接口存在，例如：

- `unordered_map::contains` 是 C++20；C++17 使用 `find`；
- `std::ranges::sort` 是 C++20；C++17 使用 `std::sort`；
- 默认比较的 `operator==` 等功能也可能需要 C++20。

本地可以显式验证：

```text
g++ -std=c++20 -O2 -Wall -Wextra -Wconversion answer.cpp -o answer
clang++ -std=c++20 -O2 -Wall -Wextra -Wconversion answer.cpp -o answer
```

若 OJ 只支持 C++17，就把 `-std=c++20` 改为 `-std=c++17`，并在提交前真实编译一次。GNU++20 可能额外提供非标准扩展；可移植代码不应把扩展误认为标准 C++。

`#include <bits/stdc++.h>` 在使用 GCC 的竞赛平台很常见，但它不是 ISO C++ 标准头文件。平台明确使用 GCC 时可以按团队习惯选择；希望同时通过 GCC、Clang 和不同标准库时，列出真正需要的头文件更稳。

## 11. 输入失败与异常：不要让异常穿过 `main`

竞赛题通常保证输入满足题面约束，因此最常见策略是：

- 第一项都读不到，说明没有输入，返回 `0`；
- 一组数据读到一半失败，返回非零；
- 对题面承诺合法的范围，不在热循环里重复做昂贵验证；
- 对必须验证的条件，明确返回错误，不继续使用半初始化数据。

不要在 `main` 外抛出一个没人捕获的异常。未捕获异常通常会调用 `std::terminate`，程序以运行时错误结束。若算法接口使用异常，应在最外层捕获并转换为明确退出状态，而且不要把错误文字打印到标准答案中：

```cpp,ignore
int main() {
    try {
        return run();
    } catch (const std::exception&) {
        return 1;
    }
}
```

在线题更常见的办法是让读取函数返回 `bool` 或让求解函数返回 `optional`/错误状态。无论选哪种方式，都要避免以下代码：

```cpp,ignore
int value;          // 尚未初始化
std::cin >> value;  // 读取可能失败
use(value);         // 失败后仍使用 value
```

`assert` 适合检查程序员认为“不可能失败”的内部不变量，不适合代替输入错误处理；发布构建可能定义 `NDEBUG` 并移除断言。

## 12. 常见错误清单

- 把 EOF 多组输入误写成先读 `T`；
- 题面有 `T`，却只处理第一组；
- 读了 `n`，循环却执行 `n-1` 或 `n+1` 次；
- `>>` 后直接 `getline`，意外读走残留换行；
- 使用 `std::ws`，把合法空行或行首空格吞掉；
- 空数组最大值初始化为零，导致全负数组答案错误；
- 在答案前打印“result =”；
- 用 `endl` 刷新每一行，造成不必要开销；
- 忘记选择正确的 C++ 标准；
- 使用 `bits/stdc++.h`，却提交到不支持它的平台；
- 输入失败后继续使用未初始化或旧的变量；
- 让异常逃出 `main`，得到 Runtime Error；
- 把函数题和 ACM 完整程序的提交格式混为一谈。

## 13. 提交前一分钟检查

- [ ] 输入是一组、`T` 组还是 EOF？
- [ ] 每组究竟读取多少字段？
- [ ] 空输入、`n=0`、`T=0` 的行为明确吗？
- [ ] `getline` 前是否正确处理了上一行？
- [ ] 标准输出中只有题目要求的字符吗？
- [ ] 空格、换行、编号和小数位是否完全符合要求？
- [ ] 是否在运算前选择了足够宽的类型？
- [ ] 读取失败后是否立刻停止，而非继续使用变量？
- [ ] 提交类型是“只填函数”还是“完整程序”？
- [ ] OJ 的 C++ 版本与本地编译命令一致吗？
- [ ] 最终代码能用题目样例和自造边界运行吗？

输入输出模板的目标不是背得更长，而是让数据边界清楚。先把题面格式翻译成“读几次、每次读什么、什么时候停止”，再写 `cin`；先把输出规范写成一个具体字符串，再写 `cout`。这样算法才不会输在最后一米。
