# 链表与树：先画指针，再写代码

反转、合并和判环训练怎样安全修改链接；树遍历、BST 验证和最近公共祖先训练怎样保存尚未完成的递归状态。

## 0. 先修回顾

单链表节点通过 `next` 表示后继，顺序表与单链、双链、循环链表的定义和完整实现见[线性表：顺序表与链表](linear_lists.md)。树节点通过孩子链接表达层次关系，树、二叉树、BST、堆和基础遍历见[树与二叉树：性质、遍历、Huffman 与堆](trees_foundations.md)。本章算法中的裸指针只表示不拥有对象的连接，测试容器负责节点生命周期。处理任意指针前都要确认它能否为空、对象由谁拥有，以及覆盖链接后是否仍能找到原后继。题目若改用 `unique_ptr` 拥有后继，改边就必须相应移动所有权，不能混用两套模型。

## 1. 母题：反转单链表

### 白话题意

输入链表 `1 -> 2 -> 3 -> nullptr`，原地改成 `3 -> 2 -> 1 -> nullptr`，返回新的头节点。空链表和只有一个节点的链表也要成立。

“原地”表示可以修改节点之间的连接，但不要为了保存全部节点再开一个数组。

### 暴力办法

先遍历链表，把每个节点指针放进数组，再倒序修改 `next`。这个办法容易想到，时间复杂度是 `O(n)`，但额外空间也是 `O(n)`。

它不是错答案，只是没有利用到一个事实：反转当前边时，只需记住“已经反好的前缀”和“尚未处理的后继”。

### 关键观察与不变量

维护三个指针：

- `previous`：已经反转好的前缀头部；
- `current`：本轮要处理的节点；
- `next`：改边前临时保存的原后继。

循环开始时保持下面的不变量：

> `previous` 指向已经正确反转的前缀，`current` 指向尚未处理的后缀；两部分合起来正好是原链表的全部节点，没有节点丢失。

顺序不能写反。必须先保存 `current->next`，再覆盖它。否则原后缀的入口会丢失。

### 伪代码

```text
previous <- null
current <- head

while current 不是 null:
    next <- current.next
    current.next <- previous
    previous <- current
    current <- next

return previous
```

### 正确性说明

开始时，已反转前缀为空，未处理后缀是整条链表，不变量成立。

每轮先保存原后继，然后把当前节点接到已反转前缀前面。于是反转前缀多一个节点，未处理后缀少一个节点，节点既没有丢失也没有重复。当 `current == nullptr` 时，未处理后缀为空，`previous` 就包含全部节点且方向完全反转，所以返回值正确。

### 复杂度

- 时间：`O(n)`，每个节点处理一次；
- 额外空间：`O(1)`，只使用几个指针。

### 完整 C++20

```cpp
#include <cassert>
#include <memory>
#include <vector>

struct ListNode {
    int value{};
    ListNode* next{};
};

ListNode* make_node(std::vector<std::unique_ptr<ListNode>>& owner, int value) {
    auto node = std::make_unique<ListNode>();
    node->value = value;
    owner.push_back(std::move(node));
    return owner.back().get();
}

ListNode* reverse_list(ListNode* head) noexcept {
    ListNode* previous = nullptr;
    ListNode* current = head;

    while (current != nullptr) {
        ListNode* const next = current->next;
        current->next = previous;
        previous = current;
        current = next;
    }
    return previous;
}

std::vector<int> values_of(const ListNode* head) {
    std::vector<int> values;
    while (head != nullptr) {
        values.push_back(head->value);
        head = head->next;
    }
    return values;
}

int main() {
    std::vector<std::unique_ptr<ListNode>> owner;
    ListNode* const one = make_node(owner, 1);
    ListNode* const two = make_node(owner, 2);
    ListNode* const three = make_node(owner, 3);
    one->next = two;
    two->next = three;

    ListNode* const reversed = reverse_list(one);
    assert((values_of(reversed) == std::vector<int>{3, 2, 1}));
    assert(one->next == nullptr);
    assert(reverse_list(nullptr) == nullptr);

    ListNode single{7, nullptr};
    assert(reverse_list(&single) == &single);
}
```

### 测试要点

至少覆盖：空链表、单节点、普通多节点。还应检查旧头节点最后指向 `nullptr`，否则可能不小心造出环。

### 常见追问

- **能递归写吗？** 能，但递归栈占 `O(n)`，长链表可能栈溢出。
- **怎样反转区间 `[left, right]`？** 先找到区间前驱，只反转区间，再接回前后两段。
- **为什么不能直接写 `current->next = previous` 后再找后继？** 原后继已经被覆盖，后面的节点会失联。

## 2. 母题：合并两个有序链表

### 白话题意

给两条非递减链表，例如 `1 -> 4 -> 7` 和 `2 -> 3 -> 8`，复用原节点把它们合成 `1 -> 2 -> 3 -> 4 -> 7 -> 8`。

### 暴力办法

把两条链表的值复制进数组，排序，再创建一条新链表。时间通常是 `O((m+n) log(m+n))`，还丢掉了“输入已经有序”和“可以复用节点”这两个条件。

### 关键观察与不变量

两条链表的头节点分别是各自剩余部分的最小值，因此较小的那个一定是合并结果的下一个节点。

用一个哑节点 `dummy` 消除“第一次接节点时没有尾节点”的特殊分支。循环开始时：

> `dummy.next ... tail` 已经是所有取出节点的完整有序合并；`first` 和 `second` 分别指向两条尚未取出后缀的最小节点。

### 伪代码

```text
dummy <- 临时节点
tail <- dummy

while first 和 second 都不是 null:
    如果 first.value <= second.value:
        tail.next <- first
        first <- first.next
    否则:
        tail.next <- second
        second <- second.next
    tail <- tail.next

tail.next <- first 不为空时取 first，否则取 second
return dummy.next
```

### 正确性说明

每轮比较两个剩余最小值，选择较小者接到结果尾部。任何未选择节点都不可能比它更小，因此结果仍有序，而且没有跳过应该先出现的节点。循环结束时，至少一条链表为空；另一条后缀本来就有序，并且其所有元素都不小于当前结果尾部，整体接上仍然有序。所有节点恰好接入一次。

### 复杂度

- 时间：`O(m+n)`；
- 额外空间：`O(1)`，不计算输入节点本身。

### 完整 C++20

```cpp
#include <cassert>
#include <memory>
#include <vector>

struct ListNode {
    int value{};
    ListNode* next{};
};

ListNode* make_node(std::vector<std::unique_ptr<ListNode>>& owner, int value) {
    auto node = std::make_unique<ListNode>();
    node->value = value;
    owner.push_back(std::move(node));
    return owner.back().get();
}

ListNode* merge_sorted(ListNode* first, ListNode* second) noexcept {
    ListNode dummy{};
    ListNode* tail = &dummy;

    while (first != nullptr && second != nullptr) {
        if (first->value <= second->value) {
            tail->next = first;
            first = first->next;
        } else {
            tail->next = second;
            second = second->next;
        }
        tail = tail->next;
    }
    tail->next = (first != nullptr) ? first : second;
    return dummy.next;
}

std::vector<int> values_of(const ListNode* head) {
    std::vector<int> values;
    while (head != nullptr) {
        values.push_back(head->value);
        head = head->next;
    }
    return values;
}

int main() {
    std::vector<std::unique_ptr<ListNode>> owner;
    ListNode* const a1 = make_node(owner, 1);
    ListNode* const a4 = make_node(owner, 4);
    ListNode* const a7 = make_node(owner, 7);
    a1->next = a4;
    a4->next = a7;

    ListNode* const b2 = make_node(owner, 2);
    ListNode* const b3 = make_node(owner, 3);
    ListNode* const b8 = make_node(owner, 8);
    b2->next = b3;
    b3->next = b8;

    const ListNode* const merged = merge_sorted(a1, b2);
    assert((values_of(merged) == std::vector<int>{1, 2, 3, 4, 7, 8}));

    ListNode only{5, nullptr};
    assert(merge_sorted(nullptr, &only) == &only);
    assert(merge_sorted(nullptr, nullptr) == nullptr);
}
```

### 测试要点

覆盖两边都为空、只有一边为空、重复值、长度差很多。使用裸指针模型时还要确认输入链表不共享节点；如果两条输入在尾部相交，直接重连可能造出环，这通常不在标准题目的前提内。

### 常见追问

- **为什么相等时选第一条？** 这使合并对来源顺序保持稳定；题目若不要求稳定，两边都可。
- **怎样合并 `k` 条有序链表？** 小根堆可做到 `O(N log k)`；分治两两合并也是 `O(N log k)`。
- **哑节点会悬空吗？** 返回的是它指向的真实输入节点，不是 `&dummy`；函数结束后哑节点销毁没有问题。

## 3. 母题：判断链表是否有环

### 白话题意

链表的某个节点可能指回前面的节点。判断从 `head` 出发是否会进入环，不能永久循环。

### 暴力办法

把访问过的节点地址放入哈希集合。再次遇到同一地址说明有环；走到 `nullptr` 说明无环。它是可靠的 `O(n)` 时间、`O(n)` 空间办法。

### 关键观察与不变量

让慢指针每次走一步，快指针每次走两步：

- 无环时，快指针最终到达 `nullptr`；
- 有环时，两者进入环后，快指针每轮相对慢指针多走一步，有限轮后一定追上。

关键安全条件是：访问 `fast->next->next` 前，必须先确认 `fast` 和 `fast->next` 都非空。

### 伪代码

```text
slow <- head
fast <- head

while fast 不是 null 且 fast.next 不是 null:
    slow <- slow.next
    fast <- fast.next.next
    如果 slow == fast:
        return true

return false
```

### 正确性说明

若链表无环，沿 `next` 前进最终必到 `nullptr`，循环安全退出并返回假。

若链表有环，慢指针最终进入环，快指针不会再遇到空指针。把环长记为 `L`，两者在环中的相对距离每轮减少一（按模 `L` 计算），因此至多再经过 `L` 轮就相遇，返回真。

### 复杂度

- 时间：`O(n)`；
- 额外空间：`O(1)`。

### 完整 C++20

```cpp
#include <cassert>

struct ListNode {
    int value{};
    ListNode* next{};
};

bool has_cycle(const ListNode* head) noexcept {
    const ListNode* slow = head;
    const ListNode* fast = head;

    while (fast != nullptr && fast->next != nullptr) {
        slow = slow->next;
        fast = fast->next->next;
        if (slow == fast) {
            return true;
        }
    }
    return false;
}

int main() {
    ListNode a{1, nullptr};
    ListNode b{2, nullptr};
    ListNode c{3, nullptr};
    a.next = &b;
    b.next = &c;
    assert(!has_cycle(&a));
    assert(!has_cycle(nullptr));

    c.next = &b;
    assert(has_cycle(&a));

    ListNode self{9, nullptr};
    self.next = &self;
    assert(has_cycle(&self));
}
```

### 测试要点

覆盖空链表、单节点无环、单节点自环、环从头开始、尾部指向中间。比较的是节点地址，不是节点值；不同节点完全可以有相同值。

### 常见追问

- **怎样找到入环节点？** 快慢指针相遇后，把一个指针放回头部；两者每次各走一步，再次相遇处就是入口。
- **怎样求环长？** 相遇后固定一个指针，另一个绕一圈并计步。
- **为什么不能修改节点做访问标记？** 输入可能只读、节点字段没有标记位，而且修改会污染调用者的数据。

## 4. 树遍历的最短回顾

前序、中序、后序分别把根放在左右子树之前、中间、之后，层序则用队列按深度逐层访问。BST 的中序序列按键有序，但普通二叉树没有这项保证。四种遍历的定义、递归推演和树性质统一见[树与二叉树：性质、遍历、Huffman 与堆](trees_foundations.md)。下面的训练重点是：把递归栈显式化时，栈里究竟保存哪些尚未完成的祖先。

## 5. 母题：非递归中序遍历

### 白话题意

按“左子树—根—右子树”的顺序返回所有节点值，不使用递归。

### 暴力办法

最直接的基线是递归：递归遍历左子树、记录根、递归遍历右子树。它时间最优，但调用栈由运行时隐式管理；树退化成链时递归深度可达 `n`。

### 关键观察与不变量

递归调用栈其实是在保存“左子树处理完后还要回来访问的祖先”。显式栈也保存这些节点：

> 栈从底到顶是一条尚未输出的祖先路径；当前指针负责继续向左寻找下一位应该输出的节点。

走不动左边时，弹出栈顶并输出，再转向它的右子树。

### 伪代码

```text
result <- 空数组
stack <- 空栈
current <- root

while current 不是 null 或 stack 不空:
    while current 不是 null:
        stack.push(current)
        current <- current.left

    current <- stack.pop()
    result.push(current.value)
    current <- current.right

return result
```

### 正确性说明

内层循环沿左边一直入栈，因此栈顶节点没有尚未访问的左后代，是下一位应输出的节点。输出后转向右子树，又用相同规则先处理它的全部左后代。这恰好重复“左—根—右”，每个节点只入栈和出栈一次。

### 复杂度

- 时间：`O(n)`；
- 额外空间：`O(h)`，`h` 是树高；最坏退化树为 `O(n)`。

### 完整 C++20

```cpp
#include <cassert>
#include <vector>

struct TreeNode {
    int value{};
    TreeNode* left{};
    TreeNode* right{};
};

std::vector<int> inorder(const TreeNode* root) {
    std::vector<int> result;
    std::vector<const TreeNode*> stack;
    const TreeNode* current = root;

    while (current != nullptr || !stack.empty()) {
        while (current != nullptr) {
            stack.push_back(current);
            current = current->left;
        }

        current = stack.back();
        stack.pop_back();
        result.push_back(current->value);
        current = current->right;
    }
    return result;
}

int main() {
    TreeNode n1{1, nullptr, nullptr};
    TreeNode n3{3, nullptr, nullptr};
    TreeNode n5{5, nullptr, nullptr};
    TreeNode n7{7, nullptr, nullptr};
    TreeNode n2{2, &n1, &n3};
    TreeNode n6{6, &n5, &n7};
    TreeNode n4{4, &n2, &n6};

    assert((inorder(&n4) == std::vector<int>{1, 2, 3, 4, 5, 6, 7}));
    assert(inorder(nullptr).empty());
}
```

### 测试要点

覆盖空树、只有根、只有左链、只有右链、左右都有的树。测试顺序本身，不要排序后再比较，否则会掩盖遍历错误。

### 常见追问

- **层序遍历怎样写？** 用队列；弹出当前节点，再把非空左右孩子入队。
- **后序为什么更难？** 根必须等左右子树都完成；可以记录上次访问节点，或用“节点+是否展开”状态。
- **显式栈是否真的省空间？** 渐进空间仍是 `O(h)`；优势是容量和失败方式更可控，不依赖递归调用栈。

## 6. 训练：一份程序写全四种二叉树遍历

### 白话题意

给定一棵普通二叉树，分别返回：

- 前序：根 → 左 → 右；
- 中序：左 → 根 → 右；
- 后序：左 → 右 → 根；
- 层序：从上到下、同层从左到右。

本题返回节点值数组。节点值可以重复；遍历的是节点身份和结构，不能因为值相同就跳过节点。

### 基线办法

可以为每个目标位置反复从根查找“第几个节点”，但这会重复走树，甚至退化到 `O(n²)`。正确起点是每种顺序只访问每个节点一次。

前三种是深度优先遍历，最直接地按定义递归；层序需要先处理完较早到达的节点，使用先进先出队列。

### 伪代码

```text
preorder(node)：
    如果 node 为空：返回
    输出 node
    preorder(node.left)
    preorder(node.right)

inorder(node)：
    如果 node 为空：返回
    inorder(node.left)
    输出 node
    inorder(node.right)

postorder(node)：
    如果 node 为空：返回
    postorder(node.left)
    postorder(node.right)
    输出 node

level_order(root)：
    如果 root 为空：返回空
    root 入队
    while 队列非空：
        node = 队首出队
        输出 node
        若左孩子非空：左孩子入队
        若右孩子非空：右孩子入队
```

### 不变量与正确性

对递归遍历做树结构归纳。空树返回空序列正确。假设左右子树各自能按要求输出：

- 前序把根放在两棵子树之前；
- 中序把根放在左右子树之间；
- 后序把根放在两棵子树之后。

这恰好分别符合三种定义，所以递归正确。

层序的不变量是：**每轮开始时，队列从前到后保存所有已发现但尚未输出的节点，并且按层序排列。** 弹出最早发现的节点，再按左、右顺序加入下一层孩子，保持该顺序。队列清空时每个可达节点恰好输出一次。

### 复杂度

四种遍历各自都是：

- 时间 `O(n)`；
- 返回数组 `O(n)`；
- 递归前/中/后序额外调用栈 `O(h)`，`h` 是树高；
- 层序额外队列 `O(w)`，`w` 是树的最大宽度。

平衡树的 `h` 约为 `log n`，但完全偏斜的树有 `h = n`。深度由外部输入控制时，递归实现可能耗尽程序栈；应设置深度上限或改成显式栈。把递归代码写得短，不会让栈空间变成 `O(1)`。

### 完整 C++20

```cpp
#include <cassert>
#include <queue>
#include <vector>

struct TreeNode {
    int value{};
    TreeNode* left{};
    TreeNode* right{};
};

void preorder_visit(const TreeNode* node, std::vector<int>& output) {
    if (node == nullptr) {
        return;
    }
    output.push_back(node->value);
    preorder_visit(node->left, output);
    preorder_visit(node->right, output);
}

void inorder_visit(const TreeNode* node, std::vector<int>& output) {
    if (node == nullptr) {
        return;
    }
    inorder_visit(node->left, output);
    output.push_back(node->value);
    inorder_visit(node->right, output);
}

void postorder_visit(const TreeNode* node, std::vector<int>& output) {
    if (node == nullptr) {
        return;
    }
    postorder_visit(node->left, output);
    postorder_visit(node->right, output);
    output.push_back(node->value);
}

std::vector<int> preorder(const TreeNode* root) {
    std::vector<int> output;
    preorder_visit(root, output);
    return output;
}

std::vector<int> inorder(const TreeNode* root) {
    std::vector<int> output;
    inorder_visit(root, output);
    return output;
}

std::vector<int> postorder(const TreeNode* root) {
    std::vector<int> output;
    postorder_visit(root, output);
    return output;
}

std::vector<int> level_order(const TreeNode* root) {
    if (root == nullptr) {
        return {};
    }

    std::vector<int> output;
    std::queue<const TreeNode*> pending;
    pending.push(root);

    while (!pending.empty()) {
        const TreeNode* const node = pending.front();
        pending.pop();
        output.push_back(node->value);
        if (node->left != nullptr) {
            pending.push(node->left);
        }
        if (node->right != nullptr) {
            pending.push(node->right);
        }
    }
    return output;
}

int main() {
    TreeNode n4{4, nullptr, nullptr};
    TreeNode n5{5, nullptr, nullptr};
    TreeNode n2{2, &n4, &n5};
    TreeNode n3{3, nullptr, nullptr};
    TreeNode n1{1, &n2, &n3};

    assert(preorder(&n1) == std::vector<int>({1, 2, 4, 5, 3}));
    assert(inorder(&n1) == std::vector<int>({4, 2, 5, 1, 3}));
    assert(postorder(&n1) == std::vector<int>({4, 5, 2, 3, 1}));
    assert(level_order(&n1) == std::vector<int>({1, 2, 3, 4, 5}));

    assert(preorder(nullptr).empty());
    assert(inorder(nullptr).empty());
    assert(postorder(nullptr).empty());
    assert(level_order(nullptr).empty());

    TreeNode only{9, nullptr, nullptr};
    assert(preorder(&only) == std::vector<int>({9}));
    assert(level_order(&only) == std::vector<int>({9}));
}
```

### 自测与边界

- 空树、单节点；
- 只有左链、只有右链；
- 完全树与不平衡树；
- 重复节点值，确认没有错误去重；
- 四个输出长度都应等于节点数；
- 前序首元素、后序末元素、层序首元素都应是根；
- 构造很深的链时，不要用“真的把进程栈打爆”作为测试，应改用显式栈版本验证大深度。

### 常见追问

- **怎样把前序改成非递归？** 显式栈先压右孩子、再压左孩子，让左侧先弹出。
- **非递归后序为什么更复杂？** 节点要等左右子树都处理后才输出，可用“节点 + 是否展开”状态或两个栈。
- **层序怎样按层分组？** 每轮先记录当前队列长度，只处理这批节点，它们的孩子留给下一轮。
- **前序和中序能否唯一重建树？** 节点键唯一且遍历合法时可以；有重复值时还需额外身份信息或规则。

## 7. 母题：验证二叉搜索树

### 白话题意

判断一棵二叉树是否满足：任意节点的左子树所有值都严格小于它，右子树所有值都严格大于它。本题不允许重复键。

只比较一个节点和直接孩子不够。下面这棵树中 `12 > 5`，看起来是 `5` 的合法右孩子，但它位于根 `10` 的左子树里，因此违反了祖先 `10` 施加的上界。

```text
      10
     /  \
    5   15
     \
      12
```

### 暴力办法

对每个节点扫描整个左子树找最大值、扫描右子树找最小值，再递归验证。最坏需要 `O(n^2)` 时间。

另一条不错的基线是中序遍历并检查结果严格递增，时间 `O(n)`、额外数组 `O(n)`。

### 关键观察与不变量

从根走向某个节点时，祖先会共同限定它的合法开区间。例如走到根的左边，上界变成根值；再向右走，下界变成当前值，但祖先上界仍然有效。

> 递归函数接收当前节点允许的排他下界和上界；只要当前值在区间内，并且两棵子树在收紧后的区间内合法，当前子树就合法。

用 `std::optional<std::int64_t>` 表示“没有边界”，避免拿 `INT_MIN`/`INT_MAX` 当哨兵后误伤边界值。

### 伪代码

```text
validate(node, lower, upper):
    如果 node 是 null: return true
    如果 lower 存在且 node.value <= lower: return false
    如果 upper 存在且 node.value >= upper: return false

    return validate(node.left, lower, node.value)
       and validate(node.right, node.value, upper)
```

### 正确性说明

空树满足定义。对非空节点，区间检查保证它满足全部祖先施加的限制。左递归把当前值设为新上界，右递归把当前值设为新下界，因此所有后代都满足与当前节点及更早祖先的关系。反过来，合法 BST 的每个节点必然处于这些祖先界限之间，所以算法不会误拒绝。

### 复杂度

- 时间：`O(n)`；
- 递归栈：`O(h)`，最坏 `O(n)`。

### 完整 C++20

```cpp
#include <cassert>
#include <cstdint>
#include <optional>

struct TreeNode {
    int value{};
    TreeNode* left{};
    TreeNode* right{};
};

bool valid_range(const TreeNode* node,
                 std::optional<std::int64_t> lower,
                 std::optional<std::int64_t> upper) {
    if (node == nullptr) {
        return true;
    }

    const std::int64_t value = node->value;
    if (lower.has_value() && value <= *lower) {
        return false;
    }
    if (upper.has_value() && value >= *upper) {
        return false;
    }

    return valid_range(node->left, lower, value) &&
           valid_range(node->right, value, upper);
}

bool is_bst(const TreeNode* root) {
    return valid_range(root, std::nullopt, std::nullopt);
}

int main() {
    TreeNode n1{1, nullptr, nullptr};
    TreeNode n3{3, nullptr, nullptr};
    TreeNode n2{2, &n1, &n3};
    assert(is_bst(&n2));
    assert(is_bst(nullptr));

    TreeNode twelve{12, nullptr, nullptr};
    TreeNode five{5, nullptr, &twelve};
    TreeNode fifteen{15, nullptr, nullptr};
    TreeNode ten{10, &five, &fifteen};
    assert(!is_bst(&ten));

    TreeNode duplicate{2, nullptr, nullptr};
    n2.right = &duplicate;
    assert(!is_bst(&n2));
}
```

### 测试要点

一定要包含“深层节点违反祖先界限”的用例、重复值，以及整数最小值/最大值附近的节点。题目若规定重复值统一放左侧或右侧，边界是否排他也要相应修改。

### 常见追问

- **中序法能否只保存上一个值？** 能，把额外数组降为 `O(h)` 递归栈加一个前驱状态。
- **为什么边界用 64 位？** 节点是 `int` 时，64 位能容纳其全部值；这里又用 `optional`，不会与真实节点值冲突。
- **BST 查找复杂度一定是 `O(log n)` 吗？** 不是；只有树高受控时才是，退化链最坏 `O(n)`。

## 8. 进阶母题：普通二叉树的最近公共祖先

### 白话题意

给一棵普通二叉树和其中两个节点 `p`、`q`，找到离它们最近、同时是二者祖先的节点。节点可以是自己的祖先。本题保证两个目标都在树中。

### 暴力办法

分别从根找到通向 `p` 和 `q` 的两条路径，再从头比较，最后一个相同节点就是答案。时间 `O(n)`，但要保存两条最多长 `h` 的路径。

### 关键观察与不变量

后序递归让每棵子树向上报告：“我这里找到了 `p`、`q`，还是两者的最近公共祖先？”

- 当前节点就是 `p` 或 `q`，报告当前节点；
- 左右子树都报告非空，说明两个目标分居两侧，当前节点就是答案；
- 只有一侧非空，把那侧的报告向上传；
- 两侧都空，报告空。

### 伪代码

```text
lca(node, p, q):
    如果 node 是 null 或 node == p 或 node == q:
        return node

    left <- lca(node.left, p, q)
    right <- lca(node.right, p, q)

    如果 left 和 right 都非空: return node
    如果 left 非空: return left
    否则: return right
```

### 正确性说明

对任意子树归纳。空树正确报告空；目标节点正确报告自己。若两个子树都报告非空，按照归纳假设，左右两边分别包含目标或已经找到答案，因此当前节点是第一次汇合处，也就是最近公共祖先。若只有一边报告非空，当前子树内已知目标都在那一边，更近的答案也只能在那里，直接上传即可。

### 复杂度

- 时间：`O(n)`，最坏访问整棵树；
- 递归栈：`O(h)`。

### 完整 C++20

```cpp
#include <cassert>

struct TreeNode {
    int value{};
    TreeNode* left{};
    TreeNode* right{};
};

const TreeNode* lowest_common_ancestor(const TreeNode* root,
                                       const TreeNode* first,
                                       const TreeNode* second) {
    if (root == nullptr || root == first || root == second) {
        return root;
    }

    const TreeNode* const left =
        lowest_common_ancestor(root->left, first, second);
    const TreeNode* const right =
        lowest_common_ancestor(root->right, first, second);

    if (left != nullptr && right != nullptr) {
        return root;
    }
    return (left != nullptr) ? left : right;
}

int main() {
    TreeNode n7{7, nullptr, nullptr};
    TreeNode n4{4, nullptr, nullptr};
    TreeNode n6{6, nullptr, nullptr};
    TreeNode n2{2, &n7, &n4};
    TreeNode n5{5, &n6, &n2};
    TreeNode n0{0, nullptr, nullptr};
    TreeNode n8{8, nullptr, nullptr};
    TreeNode n1{1, &n0, &n8};
    TreeNode n3{3, &n5, &n1};

    assert(lowest_common_ancestor(&n3, &n5, &n1) == &n3);
    assert(lowest_common_ancestor(&n3, &n5, &n4) == &n5);
    assert(lowest_common_ancestor(&n3, &n5, &n5) == &n5);
}
```

### 测试要点

覆盖目标分居根两侧、一个目标是另一个的祖先、两个参数是同一节点。上面的标准函数依赖“两个目标都存在”的题目条件；真实接口若不能保证，需要同时返回找到目标的数量，避免只存在一个目标时误报它为答案。

### 常见追问

- **BST 中能更快吗？** 能。若两值都小于当前节点就向左，两值都大于就向右，否则当前节点是分叉点。
- **有父指针怎么办？** 可以求两节点深度，先让更深者上移，再同步上移。
- **有很多次 LCA 查询怎么办？** 可研究倍增、Euler Tour + RMQ；先问清树是否变化和查询规模。

## 9. 递归栈：代码很短，不代表空间是零

递归函数每深入一层，都要保存返回地址、参数和局部状态。树高为 `h` 时，递归栈通常是 `O(h)`：

- 平衡二叉树的 `h` 约为 `log n`；
- 完全偏斜的树，`h` 可以达到 `n`；
- 深度来自外部输入时，极深递归可能让程序栈溢出。

面试回答复杂度时，不要只说“没有新建数组，所以空间 `O(1)`”。递归栈也属于额外空间。要不要改成显式栈取决于深度上界、语言环境和题目要求，而不是“递归一定不好”。

## 10. 常见错误清单

- 反转链表时没有先保存原后继；
- 解引用前没有检查 `nullptr`；
- 用节点值判断是否是同一节点，而不是比较地址；
- 合并链表后仍假设原来的两个头保持原结构；
- 只比较 BST 节点与直接孩子；
- 忘记重复值是否允许是题目定义的一部分；
- 把递归栈漏出空间复杂度；
- 返回了局部临时节点的地址；
- 测试先排序结果，导致错误遍历也能通过。

## 11. 练习

先写出不变量和三组边界测试，再写代码。

1. 删除链表倒数第 `k` 个节点，要求一次主扫描。
2. 找到无环单链表的中点；偶数长度时返回第二个中点。
3. 返回二叉树每一层的节点值。
4. 找 BST 中第 `k` 小的值。
5. 验证一棵二叉树是否高度平衡：每个节点左右子树高度差不超过一。

## 12. 练习答案与思路

### 练习 1

放一个哑节点在头前，让 `fast` 先走 `k` 步，再让 `slow`、`fast` 同步走到 `fast->next == nullptr`。此时 `slow` 指向待删节点的前驱。哑节点解决了“删除原头”的特殊情况。需要先验证 `k > 0` 且链表长度至少为 `k`。

### 练习 2

慢指针每次一步、快指针每次两步。循环条件使用 `fast != nullptr && fast->next != nullptr`；循环结束时慢指针就在中点。偶数长度时，这个写法得到第二个中点。

### 练习 3

使用队列做 BFS。每轮先记录当前队列长度 `level_size`，只弹出这 `level_size` 个节点并收集为一层；它们的孩子进入队列，留给下一轮。时间 `O(n)`，队列最宽可达 `O(w)`。

### 练习 4

BST 中序遍历严格递增。用显式栈进行中序遍历，每弹出一个节点就把计数加一，计数等于 `k` 时返回。时间最坏 `O(n)`，空间 `O(h)`；必须处理 `k` 越界。

### 练习 5

后序递归返回子树高度；若任一子树已经不平衡，或左右高度差大于一，就返回一个专门的失败状态。不要对每个节点另算一次高度，否则退化树可能达到 `O(n^2)`。一次后序遍历可以做到 `O(n)` 时间、`O(h)` 递归栈。

## 13. 面试前自检

你应该能不看模板回答：

1. 反转链表的三个指针分别表示什么？
2. 快慢指针为何一定能在环内相遇？
3. 裸指针在本章中是否拥有节点？
4. 中序遍历的显式栈保存了什么？
5. 为什么 BST 验证要携带祖先边界？
6. `O(h)` 递归栈什么时候会退化为 `O(n)`？
7. LCA 函数依赖了什么输入前提？

能写出代码只是第一步。能说出不变量、所有权和失败边界，才说明你真正掌握了这类题。
