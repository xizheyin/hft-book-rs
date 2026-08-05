# 字符串算法：先说明“字符”是什么

字符串题最常见的隐藏前提不是算法，而是“字符”两个字。对纯 ASCII 文本，一个字节就是一个字符；对 UTF-8 文本，一个人眼看到的字符可能占多个字节，多个 Unicode 码点还可能共同组成一个字形。若不先说明文本模型，代码即使通过了英文样例，也可能没有解决真实需求。

本章先把边界说清，再学习四组常用模式：频次统计、分词与精确解析、KMP 字符串匹配和 Trie 前缀查询。每个母题都先写语言无关伪代码，再翻译成可独立运行的 C++20。

> **事实边界**：这些是通用算法训练，不是 DeepSeek、九坤或任何公司的官方真题。KMP 和 Trie 是否属于某场面试的重点，取决于具体岗位和当次流程；基础不稳时，先掌握频次、扫描和解析，不要被进阶名词打乱顺序。

## 0. 先确定学习优先级

| 优先级 | 内容 | 学完应能做到什么 |
|---|---|---|
| 必须掌握 | 字节/ASCII/UTF-8 边界、频次数组、线性扫描、tokenize | 面对字符串题先定义语义，不因 `char` 符号或空 token 写错 |
| 建议掌握 | KMP 的前缀表与匹配 | 能在 `O(n+m)` 时间做精确字节串匹配，并解释为什么不会退回文本指针 |
| 进阶选读 | Trie 前缀树 | 在大量前缀查询中进行结构选择，并理解它的内存代价 |
| 按岗位深入 | Unicode 规范化、分词库、后缀结构、Aho–Corasick | 这些需要专门语义和库支持，不属于本章的入门主线 |

## 1. `std::string` 的长度到底是什么

`std::string` 保存一串 `char`，`size()` 返回保存了多少个字节。它不自动理解 Unicode。

### 1.1 ASCII

ASCII 使用 `0..127` 的单字节编码。英文字母、数字和常见英文标点都在这个范围内。若题目明确说输入仅含小写英文字母，`word[i] - 'a'` 可以映射到 `0..25`，但仍要在使用前验证范围。

### 1.2 UTF-8

UTF-8 使用一到四个字节编码一个 Unicode 码点。因此：

- `text.size()` 是字节数，不一定是码点数；
- `text[i]` 取得一个字节，不一定是完整字符；
- 按字节反转可能破坏 UTF-8；
- 两段看起来相同的文字还可能使用不同的 Unicode 规范化形式。

若题目要求“按 Unicode 码点”或“按用户看到的字形”处理，应使用合适的 Unicode 库，并明确规范化、大小写和区域设置。本章的 KMP 与 Trie 都会清楚注明自己的输入模型，不假装几行 C++ 就解决了完整 Unicode 文本处理。

### 1.3 `char` 可能有符号

在一些平台上，`char` 是有符号类型。把值大于 127 的字节直接当数组下标，可能得到负数。要把任意字节映射到 `0..255`，先转换为 `unsigned char`：

```cpp,ignore
const auto index = static_cast<unsigned char>(ch);
```

## 2. 母题一：判断两个字节串是否互为异位词

### 2.1 白话题意

给定两个 `std::string`。本题把它们视为**字节序列**，大小写敏感，空格和标点也参与比较。若二者包含完全相同的字节，且每种字节出现次数相同，就返回真。

例如：

```text
"listen" 与 "silent" → true
"Ab" 与 "ab"         → false
```

对 ASCII 输入，这就是常见的字符异位词。对 UTF-8 输入，它只能回答“编码字节的多重集合是否相同”，不能代替 Unicode 规范化后的语言学判断。

### 2.2 伪代码

```text
如果两个输入的字节长度不同：返回 false

创建 256 个计数器，初始为 0
对 left 中每个字节：对应计数加 1
对 right 中每个字节：对应计数减 1

如果所有计数都为 0：返回 true
否则返回 false
```

### 2.3 为什么正确

每个计数器记录：

> 该字节在 `left` 中的出现次数，减去它在 `right` 中的出现次数。

全部计数为零，当且仅当每种字节在两边出现次数都相同。长度检查不是正确性所必需，但能尽早拒绝明显不可能的输入。

### 2.4 复杂度

设两个字符串总长度为 `n`，时间 `O(n + 256)`，通常简写为 `O(n)`。计数数组固定为 256 项，额外空间 `O(1)`。

### 2.5 完整 C++20 实现

```cpp
#include <array>
#include <cassert>
#include <cstddef>
#include <string>
#include <string_view>

[[nodiscard]] bool are_byte_anagrams(std::string_view left,
                                     std::string_view right) {
    if (left.size() != right.size()) {
        return false;
    }

    std::array<std::ptrdiff_t, 256> counts{};
    for (const char ch : left) {
        ++counts[static_cast<unsigned char>(ch)];
    }
    for (const char ch : right) {
        --counts[static_cast<unsigned char>(ch)];
    }

    for (const std::ptrdiff_t count : counts) {
        if (count != 0) {
            return false;
        }
    }
    return true;
}

int main() {
    assert(are_byte_anagrams("listen", "silent"));
    assert(are_byte_anagrams("", ""));
    assert(are_byte_anagrams("a a!", "!aa "));
    assert(!are_byte_anagrams("Ab", "ab"));
    assert(!are_byte_anagrams("abc", "ab"));

    // 验证高位字节不会因 char 为有符号类型而变成负下标。
    const std::string high_a(1, static_cast<char>(0xFF));
    const std::string high_b(1, static_cast<char>(0xFF));
    assert(are_byte_anagrams(high_a, high_b));
}
```

### 2.6 测试时还要想什么

- 两个空串；
- 长度相同但频次不同；
- 大小写是否敏感；
- 空格、标点是否忽略；本题选择“不忽略”；
- 输入是 ASCII、任意字节、Unicode 码点还是用户看到的字形。

若题目要求忽略大小写或空白，应先定义只处理 ASCII，还是使用带区域与 Unicode 规则的正规转换。不要偷偷用 `tolower` 改变题目语义。

## 3. 母题二：把一行文本 tokenize，并精确解析订单字段

### 3.1 白话题意

输入是一行 ASCII 文本：

```text
symbol side price quantity
```

字段之间可以有一个或多个 ASCII 空白。`side` 只能是 `BUY` 或 `SELL`；价格和数量必须是完整的正 64 位整数。下面是合法输入：

```text
"AAPL   BUY  101  3"
```

下面是非法输入：

```text
"AAPL BUY 101x 3"   // 数字后还有未消费字符
"AAPL HOLD 101 3"   // side 不在约定集合
"AAPL BUY -1 3"     // 价格不是正数
```

这一题的重点不是交易业务，而是练习“扫描 token → 检查字段数量 → 精确转换 → 验证语义”这一通用解析链路。

### 3.2 伪代码

```text
tokenize(line):
    tokens = 空列表
    i = 0
    当 i 未到末尾：
        跳过从 i 开始的所有 ASCII 空白
        如果已经到末尾：结束
        start = i
        向后移动 i，直到遇到空白或末尾
        把 [start, i) 加入 tokens
    返回 tokens

parse_order(line):
    tokens = tokenize(line)
    如果 token 数量不等于 4：返回非法
    如果 side 不是 BUY 或 SELL：返回非法
    把 price 和 quantity 完整解析为 int64
    如果任一转换失败、仍有剩余字符或数值不为正：返回非法
    返回拥有自己字符串数据的 Order
```

### 3.3 为什么正确

tokenize 扫描时维护：

> `tokens` 恰好包含已经扫描前缀中的全部非空字段，`i` 指向尚未处理的位置。

每轮先跳过空白，再从第一个非空白字节扫描到下一个空白，所以加入的区间恰好是一个完整且非空的 token。`i` 始终向右移动，因此不会漏掉或重复读取字节。

解析函数要求恰好四个 token，并要求 `from_chars` 成功且返回指针到达 token 末尾。因此 `101x` 不会被误当成合法的 `101`。最后的正数与方向检查建立题目要求的业务约束。

### 3.4 复杂度

设输入长度为 `n`。tokenize 每个字节至多检查常数次，时间 `O(n)`；数值解析也是线性于数字长度，总时间仍为 `O(n)`。临时 token 视图为 `O(k)`，其中 `k` 是字段数；返回对象复制 `symbol` 和 `side`，拥有相应字符串空间。

### 3.5 完整 C++20 实现

```cpp
#include <cassert>
#include <charconv>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <system_error>
#include <vector>

[[nodiscard]] bool is_ascii_space(char ch) noexcept {
    return ch == ' ' || ch == '\t' || ch == '\n' ||
           ch == '\r' || ch == '\f' || ch == '\v';
}

[[nodiscard]] std::vector<std::string_view> tokenize_ascii_whitespace(
    std::string_view input) {
    std::vector<std::string_view> tokens;
    std::size_t i = 0;

    while (i < input.size()) {
        while (i < input.size() && is_ascii_space(input[i])) {
            ++i;
        }
        if (i == input.size()) {
            break;
        }

        const std::size_t start = i;
        while (i < input.size() && !is_ascii_space(input[i])) {
            ++i;
        }
        tokens.push_back(input.substr(start, i - start));
    }
    return tokens;
}

[[nodiscard]] std::optional<std::int64_t> parse_int64_exact(
    std::string_view token) noexcept {
    if (token.empty()) {
        return std::nullopt;
    }

    std::int64_t value{0};
    const char* const begin = token.data();
    const char* const end = token.data() + token.size();
    const auto [next, error] = std::from_chars(begin, end, value);
    if (error != std::errc{} || next != end) {
        return std::nullopt;
    }
    return value;
}

struct Order {
    std::string symbol;
    std::string side;
    std::int64_t price;
    std::int64_t quantity;

    bool operator==(const Order&) const = default;
};

[[nodiscard]] std::optional<Order> parse_order(std::string_view line) {
    const auto tokens = tokenize_ascii_whitespace(line);
    if (tokens.size() != 4) {
        return std::nullopt;
    }
    if (tokens[1] != "BUY" && tokens[1] != "SELL") {
        return std::nullopt;
    }

    const auto price = parse_int64_exact(tokens[2]);
    const auto quantity = parse_int64_exact(tokens[3]);
    if (!price || !quantity || *price <= 0 || *quantity <= 0) {
        return std::nullopt;
    }

    return Order{std::string{tokens[0]}, std::string{tokens[1]},
                 *price, *quantity};
}

int main() {
    assert((tokenize_ascii_whitespace("  a\tb  c ") ==
            std::vector<std::string_view>{"a", "b", "c"}));
    assert(tokenize_ascii_whitespace(" \t\n").empty());

    const auto order = parse_order("AAPL   BUY  101  3");
    assert(order.has_value());
    assert((*order == Order{"AAPL", "BUY", 101, 3}));

    assert(!parse_order("AAPL HOLD 101 3").has_value());
    assert(!parse_order("AAPL BUY 101x 3").has_value());
    assert(!parse_order("AAPL BUY -1 3").has_value());
    assert(!parse_order("AAPL BUY 101").has_value());
}
```

### 3.6 `string_view` 的生命周期边界

tokenizer 返回的 `string_view` 不拥有字符，它们只指向原始 `input` 的区间。只要调用方还在使用这些视图，原字符串就必须仍然存在，且不能发生让底层存储失效的修改。

本例的 `parse_order` 在返回前把 `symbol` 和 `side` 复制进 `std::string`，因此返回对象不依赖原始行的生命周期。若为了省复制而把视图长期保存进对象，必须把所有权关系写清楚，否则很容易产生悬空视图。

### 3.7 常见解析追问

- 逗号分隔格式是否保留空字段？`A,,B` 中间的空字段可能有业务含义，不能照搬“折叠空白”的政策；
- 是否允许引号和转义？若允许，普通 `split(',')` 不足以解析 CSV；
- `from_chars` 不跳过前导空白，本例已经由 tokenize 去掉字段间空白；
- 输入超过 `int64_t` 时 `from_chars` 会报告范围错误，不能静默截断；
- 不可信输入还要限制行长、字段长和字段数量，避免无界内存增长。

## 4. 母题三：KMP 查找所有出现位置

KMP 属于**建议掌握**。第一次刷字符串题时，先把普通扫描、频次和窗口练稳；需要在线性时间精确匹配，或面试明确要求手写字符串匹配时，再深入这一节。

### 4.1 白话题意

给定字节串 `text` 和 `pattern`，返回 `pattern` 在 `text` 中所有起始字节下标，允许重叠。

```text
text = "aaaa", pattern = "aa"
结果 = [0, 1, 2]
```

本题规定空模式在每个字节边界都匹配：长度为 `n` 的文本返回 `0..n`。这是一个接口选择，不是唯一可能定义。

最直接的算法从每个文本位置重新比较，最坏可能达到 `O(nm)`。KMP 的关键是：发生失配时，已经匹配的模式前缀本身包含信息，不必把文本指针退回去。

### 4.2 前缀表表示什么

对模式的每个前缀 `pattern[0..i]`，定义：

```text
prefix[i] = 这个前缀的最长“真前缀”，同时也是它的后缀的长度
```

“真前缀”不能等于整个字符串。例如 `"abab"` 的最长相同真前后缀是 `"ab"`，长度为 2。

### 4.3 伪代码

```text
build_prefix(pattern):
    prefix 全部初始化为 0
    matched = 0
    对 i 从 1 到 pattern.length - 1：
        当 matched > 0 且 pattern[i] != pattern[matched]：
            matched = prefix[matched - 1]
        如果 pattern[i] == pattern[matched]：
            matched += 1
        prefix[i] = matched
    返回 prefix

find_all(text, pattern):
    如果 pattern 为空：返回所有字节边界 0..text.length
    prefix = build_prefix(pattern)
    matched = 0
    依次扫描 text[i]：
        当 matched > 0 且 text[i] != pattern[matched]：
            matched = prefix[matched - 1]
        如果 text[i] == pattern[matched]：
            matched += 1
        如果 matched == pattern.length：
            记录 i + 1 - pattern.length
            matched = prefix[matched - 1]   // 允许重叠匹配
    返回全部位置
```

### 4.4 为什么正确

扫描过程中，`matched` 表示：

> 已处理文本后缀与模式前缀相同的最长长度。

发生失配时，任何仍可能延续的候选都必须既是已匹配片段的后缀，又是模式前缀。`prefix[matched-1]` 正好给出其中最长者；继续失败就沿前缀表寻找更短候选。这样不会漏掉可能匹配，也不需要重新检查已经知道相等的文本字符。

当 `matched == pattern.length` 时，模式全部字符与结束于 `i` 的文本片段相同，所以起点是 `i+1-pattern.length`。记录后回退到最长真前后缀，保留了下一个重叠匹配可能使用的部分。

### 4.5 复杂度

构造前缀表时间 `O(m)`、空间 `O(m)`。匹配时，文本指针只向前；`matched` 的增加与沿前缀表的总回退次数都是线性的，因此匹配时间 `O(n)`。总时间 `O(n+m)`，返回结果空间另计。

### 4.6 完整 C++20 实现

```cpp
#include <cassert>
#include <cstddef>
#include <numeric>
#include <string_view>
#include <vector>

[[nodiscard]] std::vector<std::size_t> prefix_function(
    std::string_view pattern) {
    std::vector<std::size_t> prefix(pattern.size(), 0);
    for (std::size_t i = 1; i < pattern.size(); ++i) {
        std::size_t matched = prefix[i - 1];
        while (matched > 0 && pattern[i] != pattern[matched]) {
            matched = prefix[matched - 1];
        }
        if (pattern[i] == pattern[matched]) {
            ++matched;
        }
        prefix[i] = matched;
    }
    return prefix;
}

[[nodiscard]] std::vector<std::size_t> find_all_kmp(
    std::string_view text,
    std::string_view pattern) {
    if (pattern.empty()) {
        std::vector<std::size_t> boundaries(text.size() + 1);
        std::iota(boundaries.begin(), boundaries.end(), std::size_t{0});
        return boundaries;
    }

    const auto prefix = prefix_function(pattern);
    std::vector<std::size_t> matches;
    std::size_t matched = 0;

    for (std::size_t i = 0; i < text.size(); ++i) {
        while (matched > 0 && text[i] != pattern[matched]) {
            matched = prefix[matched - 1];
        }
        if (text[i] == pattern[matched]) {
            ++matched;
        }
        if (matched == pattern.size()) {
            matches.push_back(i + 1 - pattern.size());
            matched = prefix[matched - 1];
        }
    }
    return matches;
}

int main() {
    assert((prefix_function("ababaca") ==
            std::vector<std::size_t>{0, 0, 1, 2, 3, 0, 1}));
    assert((find_all_kmp("aaaa", "aa") ==
            std::vector<std::size_t>{0, 1, 2}));
    assert((find_all_kmp("abcxabcdabxabcdabcdabcy", "abcdabcy") ==
            std::vector<std::size_t>{15}));
    assert(find_all_kmp("abc", "z").empty());
    assert((find_all_kmp("abc", "") ==
            std::vector<std::size_t>{0, 1, 2, 3}));
}
```

### 4.7 测试时还要想什么

- 空文本、空模式，以及二者都空；
- 模式比文本长；
- 没有匹配；
- 大量重复字符，例如 `aaaa` 中查 `aa`；
- 是否返回全部匹配、第一处匹配，是否允许重叠；
- 下标是字节下标、码点下标还是用户看到的字符下标。

本例按字节比较。UTF-8 中若只要求寻找完全相同的已编码字节片段，KMP 仍然能工作；但返回的是字节位置，也没有处理规范化等价。

## 5. 母题四：Trie 支持单词与前缀查询

Trie 属于**进阶选读**。它不是“字符串题必用结构”。当数据量不大，或只做少量查询时，排序后的 `vector<string>`、哈希集合甚至线性扫描可能更简单、更省内存。

### 5.1 白话题意

维护一组只含小写 ASCII 字母 `a..z` 的单词，支持：

- `insert(word)`：加入单词；
- `contains(word)`：查询完整单词是否存在；
- `starts_with(prefix)`：查询是否至少有一个已插入单词以该前缀开头。

本例允许空字符串成为一个完整单词。非法字符会被拒绝，而不是悄悄映射到错误位置。

### 5.2 伪代码

```text
每个节点保存：
    26 个可选子节点
    terminal：是否有单词恰好在此结束
整棵 Trie 另保存 distinct_words：已插入的不同单词数

insert(word):
    先验证每个字符都在 a..z
    node = root
    依次读取字符 ch：
        index = ch - 'a'
        若对应子节点不存在：创建它
        node = 对应子节点
    若 node.terminal 原本为 false：
        node.terminal = true
        distinct_words += 1

walk(text):
    node = root
    依次读取字符 ch：
        若对应子节点不存在：返回“路径不存在”
        node = 对应子节点
    返回 node

contains(word):
    node = walk(word)
    返回 node 存在且 node.terminal

starts_with(prefix):
    返回 distinct_words > 0 且 walk(prefix) 存在
```

### 5.3 为什么正确

根到某节点的路径标签，恰好是从插入单词前缀逐字符创建出来的字符串。插入完整单词后，只在最后节点设置 `terminal`，所以：

- `walk(prefix)` 成功，当且仅当某个已插入单词拥有这条前缀路径；
- `contains(word)` 还要求终点为 `terminal`，从而区分“存在这个完整单词”和“它只是更长单词的前缀”。

例如只插入 `apple` 后，`starts_with("app")` 为真，但 `contains("app")` 为假。

### 5.4 复杂度

长度为 `L` 的插入、完整查询和前缀查询，时间都是 `O(L)`。若所有单词总字符数为 `S`，节点数最坏为 `O(S)`。

本例每个节点固定保存 26 个智能指针，查找简单，但稀疏时内存开销很大。真实系统可比较压缩边、稀疏映射、排序数组或专用紧凑 Trie；选择需要结合字符集、查询量和内存测量。

### 5.5 完整 C++20 实现

```cpp
#include <array>
#include <cassert>
#include <cstddef>
#include <memory>
#include <stdexcept>
#include <string_view>

class LowercaseTrie {
public:
    void insert(std::string_view word) {
        validate(word);  // 先完整验证，避免失败时只插入一半。

        Node* node = &root_;
        for (const char ch : word) {
            const std::size_t index = static_cast<std::size_t>(ch - 'a');
            if (!node->children[index]) {
                node->children[index] = std::make_unique<Node>();
            }
            node = node->children[index].get();
        }
        if (!node->terminal) {
            node->terminal = true;
            ++distinct_words_;
        }
    }

    [[nodiscard]] bool contains(std::string_view word) const {
        validate(word);
        const Node* const node = walk(word);
        return node != nullptr && node->terminal;
    }

    [[nodiscard]] bool starts_with(std::string_view prefix) const {
        validate(prefix);
        return distinct_words_ != 0 && walk(prefix) != nullptr;
    }

private:
    struct Node {
        std::array<std::unique_ptr<Node>, 26> children{};
        bool terminal{false};
    };

    static void validate(std::string_view text) {
        for (const char ch : text) {
            if (ch < 'a' || ch > 'z') {
                throw std::invalid_argument{"trie accepts only lowercase ASCII"};
            }
        }
    }

    [[nodiscard]] const Node* walk(std::string_view text) const noexcept {
        const Node* node = &root_;
        for (const char ch : text) {
            const std::size_t index = static_cast<std::size_t>(ch - 'a');
            if (!node->children[index]) {
                return nullptr;
            }
            node = node->children[index].get();
        }
        return node;
    }

    Node root_;
    std::size_t distinct_words_{0};
};

int main() {
    LowercaseTrie trie;
    assert(!trie.starts_with(""));
    trie.insert("apple");
    trie.insert("apply");

    assert(trie.contains("apple"));
    assert(trie.contains("apply"));
    assert(!trie.contains("app"));
    assert(trie.starts_with("app"));
    assert(!trie.starts_with("banana"));
    assert(trie.starts_with(""));
    assert(!trie.contains(""));

    trie.insert("");
    assert(trie.contains(""));

    bool rejected = false;
    try {
        trie.insert("App");
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);
    assert(!trie.contains("app"));  // 失败插入没有留下半成品单词。
}
```

### 5.6 常见追问

- **怎样删除？** 先清除终点的 `terminal`，再自底向上删除既非终点、也没有子节点的节点；不能删掉其他单词共享的前缀；
- **怎样返回所有补全？** 先走到前缀节点，再 DFS 收集所有 `terminal` 路径；输出可能很大，应支持上限；
- **字符集很大怎么办？** 固定 26 路数组不再合适，可使用稀疏映射或压缩结构；
- **为什么不总用哈希集合？** 哈希集合擅长完整键查询，但不能直接枚举共享前缀；是否值得使用 Trie 取决于前缀查询需求；
- **能否直接支持 UTF-8？** 不能把 UTF-8 的单个字节当成 Unicode 字符分支。应先确定按字节、码点还是规范化后的文本建树。

## 6. 母题五：滚动哈希筛选子串，并做精确复核

滚动哈希属于**按需选学**。它适合快速比较许多等长子串，或在二分 LCP（最长公共前缀）时重复查询子串哈希。但它是概率工具：**不同字符串可能得到相同哈希，这叫碰撞。哈希相等不能单独证明字符串相等。**

### 6.1 白话题意与输入约定

给定字节串 `text` 和非空模式 `pattern`，返回模式在文本中的全部起始字节下标，允许重叠。为展示安全边界，本题这样做：

1. 用两个不同模数的滚动哈希快速筛出候选窗口；
2. 两个哈希都相等后，再逐字节比较原文与模式；
3. 只有精确比较也相等，才把位置放进答案。

本题沿用 KMP 一节的空模式语义：空模式匹配 `0..text.size()` 的所有字节边界。所有下标都是字节下标，不是 Unicode 字符下标。

### 6.2 基线方法

从每个可能起点逐字节比较模式：

```text
for start 从 0 到 text.length - pattern.length：
    如果 text[start ... start + pattern.length) 与 pattern 完全相同：
        记录 start
```

最坏时间为 `O(nm)`。KMP 能在 `O(n+m)` 内完成精确单模式匹配；滚动哈希的价值主要出现在“很多子串比较共享同一份预处理”时，而不是无条件替代 KMP。

### 6.3 哈希定义与不变量

把每个字节编码为 `1..256`，长度为 `m` 的窗口定义为多项式：

```text
hash(s[0..m)) = s[0] × base^(m-1)
               + s[1] × base^(m-2)
               + ...
               + s[m-1]                 (mod modulus)
```

窗口右移时，减掉旧首字节的最高次项，再乘 `base` 并加入新尾字节。循环不变量是：**每轮比较前，两个窗口哈希分别等于当前长度 `m` 窗口在两个模数下的多项式值。**

使用两个模数只会降低碰撞概率，不会把概率降成数学上的零。本实现最终逐字节复核，因此返回结果仍是确定正确的。

### 6.4 伪代码

```text
如果 pattern 为空：返回全部字节边界
如果 pattern 比 text 长：返回空

计算 pattern 的双哈希
计算 text 第一个等长窗口的双哈希
计算 base^(pattern.length - 1) 在两个模数下的值

for start 遍历所有窗口起点：
    如果窗口双哈希 == pattern 双哈希：
        如果原始字节逐个比较也相等：
            记录 start

    如果还有下一个窗口：
        从哈希减掉旧首字节最高次项
        哈希乘 base，再加新尾字节

返回全部位置
```

### 6.5 为什么正确

初始窗口逐字节构造，符合哈希定义。右移公式精确删除旧首字节的贡献，并把其余项次数提升一位后加入新尾字节，所以哈希不变量保持。

任何真实匹配的字节序列完全相同，它在两个模数下的哈希也必然相同，因此不会被哈希筛选漏掉。哈希相同的候选可能是碰撞，但程序随后进行精确比较；只有原字节确实相同才输出。因此返回位置没有假阳性，也没有漏掉真实匹配。

### 6.6 复杂度

- 哈希初始化与滚动扫描：`O(n+m)`；
- 额外状态：`O(1)`，返回结果除外；
- 每个双哈希候选还要精确比较 `O(m)`。

所以在碰撞很多或真实匹配很多的最坏情况下，总时间仍可能达到 `O(nm)`。若只做一次精确模式匹配并要求确定线性最坏界，KMP 更合适。

### 6.7 完整 C++20 实现

两个模数都小于 `2^32`，相乘的中间结果能放进 `std::uint64_t`。这不是“不会碰撞”的证明，只是避免本例的模乘先溢出。

```cpp
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <numeric>
#include <string_view>
#include <vector>

struct DoubleHash {
    std::uint64_t first{};
    std::uint64_t second{};

    bool operator==(const DoubleHash&) const = default;
};

constexpr std::uint64_t kBase = 257;
constexpr std::uint64_t kMod1 = 1'000'000'007;
constexpr std::uint64_t kMod2 = 1'000'000'009;

std::uint64_t append_hash(
    std::uint64_t hash,
    std::uint64_t byte,
    std::uint64_t modulus) {
    return (hash * kBase + byte) % modulus;
}

std::uint64_t power_mod(
    std::size_t exponent,
    std::uint64_t modulus) {
    std::uint64_t result = 1;
    for (std::size_t i = 0; i < exponent; ++i) {
        result = (result * kBase) % modulus;
    }
    return result;
}

DoubleHash hash_bytes(std::string_view text) {
    DoubleHash result;
    for (const char ch : text) {
        const std::uint64_t byte =
            static_cast<unsigned char>(ch) + std::uint64_t{1};
        result.first = append_hash(result.first, byte, kMod1);
        result.second = append_hash(result.second, byte, kMod2);
    }
    return result;
}

std::uint64_t roll_hash(
    std::uint64_t current,
    std::uint64_t outgoing,
    std::uint64_t incoming,
    std::uint64_t highest_power,
    std::uint64_t modulus) {
    const std::uint64_t removed = (outgoing * highest_power) % modulus;
    current = (current + modulus - removed) % modulus;
    return append_hash(current, incoming, modulus);
}

std::vector<std::size_t> find_all_rolling_hash_verified(
    std::string_view text,
    std::string_view pattern) {
    if (pattern.empty()) {
        std::vector<std::size_t> boundaries(text.size() + 1);
        std::iota(boundaries.begin(), boundaries.end(), std::size_t{0});
        return boundaries;
    }
    if (pattern.size() > text.size()) {
        return {};
    }

    const DoubleHash target = hash_bytes(pattern);
    DoubleHash window = hash_bytes(text.substr(0, pattern.size()));
    const std::uint64_t power1 = power_mod(pattern.size() - 1, kMod1);
    const std::uint64_t power2 = power_mod(pattern.size() - 1, kMod2);
    std::vector<std::size_t> matches;

    const std::size_t last_start = text.size() - pattern.size();
    for (std::size_t start = 0; start <= last_start; ++start) {
        if (window == target && text.substr(start, pattern.size()) == pattern) {
            matches.push_back(start);  // 精确复核，哈希相等本身不够。
        }

        if (start == last_start) {
            break;
        }
        const std::uint64_t outgoing =
            static_cast<unsigned char>(text[start]) + std::uint64_t{1};
        const std::uint64_t incoming =
            static_cast<unsigned char>(text[start + pattern.size()]) +
            std::uint64_t{1};
        window.first = roll_hash(
            window.first, outgoing, incoming, power1, kMod1);
        window.second = roll_hash(
            window.second, outgoing, incoming, power2, kMod2);
    }
    return matches;
}

int main() {
    assert((find_all_rolling_hash_verified("aaaa", "aa") ==
            std::vector<std::size_t>{0, 1, 2}));
    assert((find_all_rolling_hash_verified("abcxabcd", "abc") ==
            std::vector<std::size_t>{0, 4}));
    assert(find_all_rolling_hash_verified("abc", "abcd").empty());
    assert(find_all_rolling_hash_verified("abc", "z").empty());
    assert((find_all_rolling_hash_verified("abc", "") ==
            std::vector<std::size_t>{0, 1, 2, 3}));

    // 复核接口的确定语义：所有返回窗口都与模式逐字节相等。
    const std::string_view text = "bananana";
    const std::string_view pattern = "ana";
    for (const std::size_t start :
         find_all_rolling_hash_verified(text, pattern)) {
        assert(text.substr(start, pattern.size()) == pattern);
    }
}
```

### 6.8 自测与边界

- 空文本、空模式、模式比文本长；
- 重叠匹配、大量重复字节；
- 包含 `\0` 或高位字节的 `string_view`；
- 验证窗口更新后的哈希与从头计算的哈希一致；
- 故意改成很小的模数制造碰撞，确认精确复核会过滤假阳性；
- 下标单位是否明确为字节。

### 6.9 常见追问

- **双哈希是否绝对无碰撞？** 不是。它只降低概率；需要绝对正确时要复核原文或使用确定性算法。
- **怎样比较许多任意子串？** 保存前缀哈希和幂表，让任意等长子串哈希查询为 `O(1)`；仍要定义碰撞政策。
- **怎样求两个后缀的 LCP？** 可在长度上二分并比较子串哈希，得到概率型 `O(log n)` 查询；若结果用于关键正确性判断，应复核或采用后缀数组等确定结构。
- **随机选择 base 有什么用？** 可降低针对固定参数构造碰撞的风险，但不会消除碰撞，也要记录随机种子以便复现。

## 7. 这些工具怎样选择

| 需求 | 常用起点 | 先确认什么 |
|---|---|---|
| 比较字符/字节频次 | 固定数组或哈希表 | 字符集大小、大小写、规范化 |
| 拆分并验证一行输入 | 线性扫描 + `string_view` + 精确转换 | 分隔符、空字段、引号、所有权、长度上限 |
| 在长文本中找固定模式 | 朴素匹配或 KMP | 数据规模、一次还是多次匹配、空模式语义 |
| 大量等长子串比较 | 滚动哈希作筛选 | 碰撞政策、是否需要精确复核 |
| 大量完整单词查询 | `unordered_set<string>` | 是否只问完整键 |
| 大量前缀查询/补全 | Trie 或排序字符串范围 | 字符集、内存、更新频率、输出上限 |

算法名称不是由“题目里出现了字符串”决定的。先问自己要维护的事实：频次、边界、匹配前缀，还是共享前缀结构。

## 8. 提交前检查表

- [ ] “字符”指字节、ASCII、Unicode 码点还是用户看到的字形？
- [ ] 使用字节作为数组下标前，是否转换为 `unsigned char`？
- [ ] 大小写、空格、标点和规范化规则是否明确？
- [ ] tokenize 是否应该保留连续分隔符之间的空字段？
- [ ] 数字解析是否检查了范围和未消费的尾部字符？
- [ ] 保存的 `string_view` 是否可能比原字符串活得更久？
- [ ] 空模式、重叠匹配和返回下标单位是否明确？
- [ ] 使用哈希相等时，是否明确碰撞并安排精确复核或概率政策？
- [ ] Trie 的字符集是否合法，失败插入会不会留下半成品状态？
- [ ] 返回全部匹配或全部补全时，是否考虑输出本身的大小？

## 9. 变体练习

1. 判断两个小写 ASCII 字符串是否至多相差一次替换；先写双指针，再考虑长度不同的插入/删除。
2. 编写逗号分词器，明确 `A,,B,` 的输出；再说明为什么它还不是完整 CSV 解析器。
3. 修改 KMP，只返回第一处匹配；比较接口和空间是否需要变化。
4. 为 Trie 增加安全删除和最多返回 `k` 个补全结果。
5. 给定多个模式，先用逐个 KMP 给基线，再研究 Aho–Corasick 解决了哪些重复工作；这是进阶选读，不要求第一次完成。
6. 把滚动哈希改成前缀哈希，回答任意等长子串比较；再写一个逐字节 oracle 做随机对拍，并解释为什么对拍不能证明永远无碰撞。

字符串算法真正的起点不是背 KMP，而是给文本建立准确模型。只要先说清“我比较的到底是什么”，频次、扫描、前缀表和 Trie 才能成为可靠工具，而不是在英文样例上碰巧工作的模板。
