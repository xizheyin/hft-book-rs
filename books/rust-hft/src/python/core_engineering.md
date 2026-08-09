# Python 工程基础：从对象语义到并发与原生边界

Python 常被用来写数据处理、自动化、测试、服务控制面和 AI 工具。它的代码短，但运行时并不会替程序员自动解决对象共享、并发、依赖和性能问题。本章用一条主线解释这些问题：**名字引用哪个对象，工作在哪个执行单元中完成，数据跨边界时由谁复制或持有。**

## 1. 变量保存的是名字与对象的绑定

先看一个容易误判的例子：

```python
prices = [101, 102]
backup = prices
backup.append(103)

assert prices == [101, 102, 103]
```

`backup = prices` 没有复制列表。它只是让两个名字引用同一个列表对象，所以通过任一名字修改对象，另一边都能看到。

```text
prices ─┐
        ├──> list object [101, 102, 103]
backup ─┘
```

若确实需要一个新的浅层列表，可以写 `prices.copy()` 或 `prices[:]`。这里的“浅层”表示只复制最外层容器；其中的元素若本身是可变对象，新旧容器仍会引用同一批元素。

```python
rows = [[1], [2]]
copied = rows.copy()
copied[0].append(9)

assert rows == [[1, 9], [2]]
```

判断两个值时还要区分：

- `a == b` 比较值是否相等；
- `a is b` 比较是否为同一个对象；
- `id(a)` 可帮助观察对象身份，但不应被当成持久业务编号。

函数调用也不会默认复制实参。形参是函数作用域中的新名字，它会绑定到传入对象。函数若修改一个可变对象，调用者可能看见变化；若只是让形参重新绑定到另一个对象，调用者原来的名字不会随之改变。

```python
def add_one(values: list[int]) -> None:
    values.append(1)       # 修改调用者也引用的列表

def replace(values: list[int]) -> None:
    values = [99]          # 只改变局部名字的绑定
```

## 2. 可变与不可变决定“修改”意味着什么

常见不可变对象包括整数、浮点数、布尔值、字符串、字节串和只包含不可变元素的元组。列表、字典、集合以及多数用户自定义对象通常可变。

```python
count = 10
old_count = count
count += 1

assert old_count == 10
assert count == 11
```

整数对象本身没有被原地改成 11；`count` 改为绑定另一个整数对象。相反，`list.append` 会修改原列表。

这个区别解释了可变默认参数陷阱：默认值在函数定义时创建，不是每次调用时重新创建。

```python
# 错误示例：多次调用共享同一个默认列表
def collect_bad(value: int, output: list[int] = []) -> list[int]:
    output.append(value)
    return output

# 正确起点：用 None 表示“本次调用尚未提供列表”
def collect(value: int, output: list[int] | None = None) -> list[int]:
    if output is None:
        output = []
    output.append(value)
    return output
```

闭包也保存名字的绑定，而不总是保存创建闭包那一刻的值。循环中创建回调时，可以用默认参数明确捕获本轮值：

```python
callbacks = [lambda i=i: i for i in range(3)]
assert [fn() for fn in callbacks] == [0, 1, 2]
```

这里的默认参数是不可变整数，用来冻结每轮的 `i`；不能把这条技巧误用成“可变默认参数也安全”。

## 3. 容器选择同时决定语义和成本

| 容器 | 表达的关系 | 常见操作的典型成本 |
|---|---|---|
| `list` | 有顺序、可修改的序列 | 按下标 `O(1)`；末尾追加摊还 `O(1)`；头部插入/删除 `O(n)` |
| `tuple` | 有顺序、结构固定的记录 | 按下标 `O(1)`；创建后不能替换元素 |
| `dict` | 键到值的映射 | 查询、插入通常平均 `O(1)`；最坏界不能简单写成永远 `O(1)` |
| `set` | 不重复元素的集合 | 成员查询通常平均 `O(1)` |
| `str` | Unicode 文本 | 不可变；反复 `+=` 可能产生中间对象 |
| `bytes` / `bytearray` | 原始字节 | 前者不可变，后者可变；不能和文本编码混为一谈 |

“摊还 `O(1)`”表示一长串 `append` 的平均成本是常数级。某次扩容仍可能申请更大内存并复制已有引用，因此对单次耗时有严格要求时，不能把摊还成本误说成每次固定成本。

队列若频繁从头部弹出，不应使用 `list.pop(0)`；`collections.deque` 为两端操作提供更合适的语义和成本。优先队列可使用 `heapq`，它维护的是堆序，不是完整排序。

字符串拼接大量片段时，通常先保存片段再执行 `"".join(parts)`。这让“收集”和“一次生成结果”两个阶段清楚，也避免依赖解释器是否碰巧优化连续拼接。

### 3.1 排序与比较键

`sorted(iterable)` 返回新列表，`list.sort()` 原地修改列表。两者都可以通过 `key` 说明排序依据：

```python
records = [
    {"name": "a", "score": 8},
    {"name": "b", "score": 10},
]

ranked = sorted(records, key=lambda row: row["score"], reverse=True)
```

把业务规则写进 `key`，通常比编写复杂比较函数更容易测试。排序的时间复杂度通常按 `O(n log n)` 估算，但 `key` 自身的计算和对象分配也必须计入。

## 4. 迭代器与生成器把“一次性过程”暴露出来

**可迭代对象（iterable）**能够产生迭代器；**迭代器（iterator）**保存当前位置，并通过 `next()` 逐个给出元素。迭代结束后抛出 `StopIteration`，通常由 `for` 循环代为处理。

```python
values = [10, 20, 30]
iterator = iter(values)
assert next(iterator) == 10
assert next(iterator) == 20
```

列表可以反复迭代，因为每次 `iter(values)` 都能创建新迭代器。文件对象、生成器等对象通常代表一次向前推进的过程；消费后若要重来，需要重新打开、重新创建，或事先保存结果。

带 `yield` 的函数返回生成器：

```python
from collections.abc import Iterator

def valid_lines(lines: list[str]) -> Iterator[str]:
    for line in lines:
        stripped = line.strip()
        if stripped:
            yield stripped
```

调用 `valid_lines` 时函数体不会一次执行完。每次请求下一个元素，它才继续运行到下一个 `yield`。这样可以流式处理大输入，但不表示内存一定有界：若后续又调用 `list(generator)`，全部结果仍会进入内存。

生成器表达式 `(parse(x) for x in source)` 是惰性的；列表推导式 `[parse(x) for x in source]` 会立即构造列表。选择依据是是否需要重复访问、随机下标、完整长度以及输入可能有多大。

## 5. 异常表示失败，`with` 保证退出路径清理

异常会沿调用栈向上传播，直到找到匹配的处理逻辑。只捕获能够真正处理的异常；`except Exception:` 后直接忽略会丢失故障证据。

```python
from pathlib import Path

def read_limit(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
        value = int(text.strip())
    except OSError as error:
        raise RuntimeError(f"cannot read limit from {path}") from error
    except ValueError as error:
        raise ValueError(f"limit is not an integer: {path}") from error

    if value < 0:
        raise ValueError("limit must be non-negative")
    return value
```

`raise ... from error` 保存“高层动作为何失败”和“底层原始原因”两层上下文。异常消息应说明对象和动作，但不要写入口令、令牌或完整敏感输入。

上下文管理器通过 `with` 把获取与释放放进同一个语法结构：

```python
with open("events.txt", "r", encoding="utf-8") as handle:
    first_line = handle.readline()
```

离开代码块时，无论正常返回还是抛出异常，文件都会执行清理。锁、数据库事务、临时目录也可使用同样协议。它解决的是退出路径清理，不自动保证业务操作可以回滚。

自定义上下文管理器可以实现 `__enter__` / `__exit__`，也可以使用 `contextlib.contextmanager`。若资源生命周期很复杂，优先选择已经验证过的库对象，不要只为展示语法自行实现一套资源管理。

## 6. Class 与类型标注：描述对象和接口

`class` 定义一类对象可以保存什么状态、执行什么方法。`self` 是当前实例，由方法调用语法传入：

```python
class Counter:
    def __init__(self, initial: int = 0) -> None:
        self.value = initial

    def add(self, delta: int) -> None:
        self.value += delta

counter = Counter(10)
counter.add(2)
assert counter.value == 12
```

写在 `self` 上的是实例属性，每个 `Counter` 对象各自拥有绑定。直接写在 class 代码块中的可变 class 属性会被实例共享，除非这正是所需语义，否则应在 `__init__` 中创建实例状态。

Decorator（装饰器）在函数或 class 定义完成时接收并返回一个对象，用来增加注册、包装或生成代码等行为。下面的 `@dataclass` 会根据字段标注生成初始化和比较等常用方法；`frozen=True` 阻止通过普通属性赋值修改实例，但若字段内部引用可变对象，并不会递归冻结整个对象图。

```python
from dataclasses import dataclass
from collections.abc import Iterable

@dataclass(frozen=True)
class Sample:
    value: float
    valid: bool

def mean_valid(samples: Iterable[Sample]) -> float | None:
    values = [sample.value for sample in samples if sample.valid]
    return sum(values) / len(values) if values else None
```

类型标注帮助编辑器、静态检查器和读者理解接口。普通 CPython 默认不会在函数入口自动拒绝错误类型；来自 JSON、命令行、网络和数据库的数据仍要做运行时解析与校验。

几个常用边界：

- 参数只需要“能迭代”，可写 `Iterable[T]`，不必强迫调用者提供 `list[T]`；
- 函数可能没有结果，可写 `T | None`，并明确 `None` 的业务含义；
- 固定字段的数据可以用 `dataclass`，行为接口可用 `Protocol` 或抽象基类；
- `Any` 表示跳过该处的静态约束，不表示“任意值都能安全使用”。

静态类型不能替代测试。它擅长发现接口不匹配，却通常不能证明数值范围、状态机顺序和外部副作用正确。

## 7. Module、Package、虚拟环境各解决什么

- **module** 通常是一个可导入的 `.py` 文件；
- **package** 把一组 module 组织到命名空间中，并由项目元数据描述如何构建和安装；
- **虚拟环境**为一个项目提供相对独立的解释器入口和第三方包目录；
- **锁定文件或已解析依赖清单**记录实际选择的版本，用于复现构建。

一个最小项目可以写成：

```text
project/
├── pyproject.toml
├── src/
│   └── metrics_app/
│       ├── __init__.py
│       └── statistics.py
└── tests/
    └── test_statistics.py
```

创建与使用标准库虚拟环境：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m pytest -q
```

使用 `python -m ...` 可以明确“由当前解释器运行这个 module”，减少 `pip`、`pytest` 与另一个 Python 安装意外混用的机会。虚拟环境隔离的是 Python 依赖入口，不是容器或安全沙箱；原生动态库、GPU 驱动和系统工具仍来自环境的其他部分。

导入时，module 顶层代码会执行。因此不要在 import 阶段悄悄启动线程、读取大型数据或修改外部系统。命令行入口通常放在函数中，并用下面的保护：

```python
def main() -> int:
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

这个保护对多进程尤其重要：新解释器可能重新导入主 module；若导入本身又无条件创建子进程，就会递归启动。

## 8. pytest：从行为和边界验证接口

测试应说明输入、动作和可观察结果。不要把函数内部每一行再复制到测试里，否则实现与测试可能一起犯同一个错。

```python
# src/metrics_app/statistics.py
def safe_mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None
```

```python
# tests/test_statistics.py
import pytest

from metrics_app.statistics import safe_mean

@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([2.0, 4.0], 3.0),
        ([5.0], 5.0),
        ([], None),
    ],
)
def test_safe_mean(values: list[float], expected: float | None) -> None:
    assert safe_mean(values) == expected
```

测试外部系统时先问边界在哪里：纯计算使用单元测试；数据库、文件或服务协议使用集成测试；真实进程、网络和 GPU 再放进更高层测试。Mock 只验证约定的交互，不能证明真实依赖具有相同协议、时序和故障行为。

一个可复现失败至少应记录 Python 版本、依赖版本、平台、随机种子、输入摘要和完整 traceback。修复后添加能在旧版本稳定失败的回归测试，而不是只重新运行一次看它是否碰巧通过。

## 9. CPython、引用计数与 GIL 的版本边界

**Python**是语言和标准库规范，**CPython**是最常见的一种实现。对象布局、引用计数和 Global Interpreter Lock（GIL，全局解释器锁）中的许多细节属于 CPython，实现或版本改变时不能当成永恒语言定律。

默认启用 GIL 的 CPython 中，一个进程内通常只有持有 GIL 的线程能执行 Python 对象操作。阻塞 I/O 和部分原生扩展可能在不访问 Python 对象时释放 GIL，因此线程仍可有效重叠许多 I/O 工作。它不意味着：

- Python 程序没有数据竞争；一段业务更新可能跨多条字节码并被切换；
- 所有 C/C++ 扩展都会释放 GIL；要查看扩展的明确承诺；
- 多线程 CPU 密集型 Python 代码会随核心数线性加速；
- GIL 能代替锁、队列和不可变数据设计。

从 CPython 3.13 开始，官方还提供可选的 free-threaded build，使 GIL 可以禁用。它不是所有安装的默认状态；不兼容的原生扩展还可能在导入时重新启用 GIL。面试或排障时应先说明解释器、版本、构建方式和依赖支持，再讨论并行性。即使在 free-threaded build 中，也不要依赖内置容器当前的内部锁来表达业务原子性；共享状态仍应有明确同步协议。

引用计数让许多 CPython 对象在最后一个强引用消失后很快清理，但环形引用还需要循环垃圾收集器处理。析构时机在其他 Python 实现中可能不同，所以文件、锁和事务应使用 `with` 或显式关闭，而不是依赖对象“很快被回收”。

## 10. Thread、Process 与 asyncio 怎样选择

| 方式 | 同时推进的单位 | 适合的起点 | 主要代价与风险 |
|---|---|---|---|
| `threading` | 同一进程中的线程 | 阻塞 I/O、调用会释放 GIL 的原生工作 | 共享状态竞态；默认 GIL 构建下纯 Python CPU 并行受限 |
| `multiprocessing` | 独立解释器进程 | 可拆分的 CPU 工作、需要进程隔离 | 启动、序列化、进程间通信和额外内存 |
| `asyncio` | 事件循环中的协作 Task | 大量支持异步接口的网络/I/O 操作 | 阻塞函数会卡住事件循环；取消与超时必须传播 |

异步不等于并行。一个常规事件循环通常在一个线程中运行；Task 在 `await` 交出控制权后，其他 Task 才能继续。若在协程中直接执行长时间 CPU 循环或阻塞系统调用，整个事件循环都会停住。

```python
import asyncio

async def fetch_one(name: str, delay: float) -> str:
    await asyncio.sleep(delay)  # 代表可异步等待的 I/O
    return name

async def main() -> list[str]:
    async with asyncio.TaskGroup() as group:
        tasks = [
            group.create_task(fetch_one("a", 0.02)),
            group.create_task(fetch_one("b", 0.01)),
        ]
    return [task.result() for task in tasks]

results = asyncio.run(main())
```

结构化并发让父作用域等待子任务收口，并在失败时传播取消。真实 I/O 还应设置 deadline、并发上限与背压，不能因为协程便宜就无限创建任务。

多进程会跨地址空间传递数据。`multiprocessing.Queue` 等接口通常需要序列化对象，所以把巨大数组反复发送给 worker 可能比计算更贵。还要保护主入口，使子解释器能够安全导入 module。

## 11. NumPy：形状、步长、视图与广播

Python 列表保存的是对象引用；NumPy `ndarray` 通常用一块同类型数据缓冲区，加上 `dtype`、`shape` 和 `strides` 描述数组。

```python
import numpy as np

matrix = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)

assert matrix.shape == (2, 3)
assert matrix.dtype == np.float32
```

`shape=(2,3)` 表示两行三列。`strides` 表示各维下标增加 1 时，内存地址跨过多少字节。转置或切片常能只改变描述信息并共享原缓冲区，这叫 **view（视图）**；高级索引等操作则可能复制数据。

```python
column = matrix[:, 1]  # 常为共享数据的视图
column[0] = 20
assert matrix[0, 1] == 20
```

因此不能只看到“赋值给新变量”就断定是否复制。检查 `.base`、内存共享关系和连续性，并在接口中说明调用者是否允许修改。

广播从末尾维度开始比较；两维相等，或其中一维为 1 时可以兼容。例如 `[B,D] + [D]` 会把后者逻辑上用于每一行。广播通常不先创建完整重复副本，但后续算子仍会读取相应数据，错误的形状也可能产生合法却语义错误的结果。

向量化把循环交给底层连续数据算子，常比逐元素 Python 循环快。但它不自动减少内存：表达式 `a*b + c*d` 可能产生中间数组；切片的非连续布局也可能迫使下游复制。优化前应同时测 Python 开销、内存字节、原生 Kernel 和数据转换。

## 12. Python 与 C++ 的边界要明确所有权和失败

量化与 AI 系统常让 Python 负责编排，让 C++/CUDA 负责计算密集或硬件相关部分。跨语言调用至少要回答六个问题：

1. **数据布局**：元素类型、形状、步长、字节序和对齐是否一致；
2. **所有权**：缓冲区由谁分配，谁保证它在原生代码使用期间仍存活；
3. **复制**：接口是共享视图、移动所有权，还是创建新缓冲区；
4. **线程**：原生调用是否释放 GIL，回调 Python 前怎样取得合法线程状态；
5. **失败**：C++ 异常、错误码与 Python 异常怎样转换；ABI（Application Binary Interface，应用二进制接口）规定编译后二进制怎样调用和传递数据，异常不能越过不兼容 ABI 边界；
6. **构建**：编译器、C++ ABI、Python 版本、平台和依赖动态库怎样进入 wheel 或部署产物。

所谓“零拷贝”也必须带生命周期条件。NumPy view 交给 C++ 后，若 Python 所有者先被释放，原生指针就会悬空；若 C++ 保留引用，则绑定层要让 Python 对象或共享所有权一起存活。数据没有复制，不代表没有边界检查、引用计数、线程切换或设备同步成本。

对 GPU 张量还要增加设备和异步完成边界：CPU 代码发起操作后，设备工作可能尚未完成；读取结果、回收缓冲或跨 stream 使用前需要符合框架协议的同步。不能用一次 Python 函数返回，推断 GPU 已经完成全部工作。

## 13. 常见误区

1. **“赋值会复制对象。”** 普通赋值只增加一个绑定；是否复制取决于显式操作和对象协议。
2. **“tuple 里所有东西都不可变。”** tuple 不能替换槽位，但槽位可引用可变列表。
3. **“dict 查询永远严格 `O(1)`。”** 常用实现提供平均常数行为，最坏情况和哈希成本仍需说明。
4. **“生成器一定省内存。”** 它只按需产生元素；调用者仍可累计全部结果。
5. **“有类型标注就不需要验证输入。”** 标注默认不会在运行时自动拒绝外部脏数据。
6. **“GIL 让共享数据天然安全。”** 业务操作可能跨多步，原生代码也可能释放 GIL；应写明确同步。
7. **“async 会自动使用所有 CPU 核。”** 它主要组织协作等待；CPU 并行要看进程、原生实现或 free-threaded 环境。
8. **“NumPy 切片总会复制。”** 基本切片常返回共享数据的 view，修改可能影响原数组。
9. **“调用 C++ 就一定快。”** 小工作频繁跨边界、转换数据和同步设备可能吞掉收益。

## 14. 做题与排障方法：画三张表

1. **对象表**：为每个名字写出它引用的对象、对象是否可变、是否与其他名字共享。遇到嵌套容器要分外层与内层，不能只写“已复制”。
2. **执行表**：写清线程、进程或 async Task，谁能同时推进，何处等待，何处共享状态，哪一层实际持有 GIL。不要从语法 `async` 或 `thread` 直接推出并行。
3. **数据边界表**：跨 module、进程、C++ 或 GPU 时，记录类型/形状、复制、所有者、序列化、同步与错误转换。
4. **复杂度验算**：把 Python 循环次数、容器操作、对象分配和原生批处理分别计数。平均 `O(1)`、摊还 `O(1)`和最坏 `O(n)`不能混写。
5. **最小复现**：固定解释器与依赖版本，缩小输入，保留完整 traceback；并发故障还要记录随机种子、任务顺序和超时。
6. **修复后反证**：新增回归测试，并分别覆盖空输入、单元素、共享对象、取消、异常和大数据边界。性能修复要与正确性测试分开验证。

## 15. 章末思考题与工程题

1. `a=[[1],[2]]; b=a.copy(); b[0].append(3)` 后，`a` 和 `b` 分别是什么？为什么？
2. 为什么 `list.append` 是摊还 `O(1)`，却不能保证每次调用耗时相同？
3. 生成器和列表各适合什么访问模式？一个生成器为什么可能“第二次遍历为空”？
4. `with` 在异常路径上保证什么，又不能保证什么？
5. 类型标注为什么不能替代网络输入校验与单元测试？
6. 默认 GIL 构建下，两个 Python 线程适合并行处理纯 Python CPU 循环吗？什么信息会改变答案？
7. 什么时候选择线程、进程或 `asyncio`？分别列出一个主要成本。
8. NumPy 的 view 与 copy 有什么区别？如何验证一次切片是否可能与原数组共享数据？
9. Python 把 NumPy 缓冲区交给 C++ 而不复制时，至少要维持哪些不变量？
10. 某 `asyncio` 服务吞吐突然下降，发现一个协程调用阻塞式压缩函数 500 ms。为什么它会影响其他请求？怎样验证并修复？

### 参考答案与解答

<details>
<summary>展开答案</summary>

1. `a` 与 `b` 都呈现 `[[1,3],[2]]`。`a.copy()` 只创建新的外层 list；两个外层 list 的第 0 个槽位仍指向同一个内层 list。`append(3)` 修改的是共享内层对象。若要隔离所有层，必须根据数据结构定义执行深复制或显式重建；深复制也不适合包含文件句柄等不可复制资源的任意对象图。
2. list 通常预留额外容量。多数 `append` 只写入空槽，成本近似常数；容量不足的少数调用要申请更大区域并复制已有引用，成本随当前长度增长。把一串扩容成本摊到许多追加上得到摊还 `O(1)`，但单次长尾仍存在。
3. 需要随机下标、已知长度或反复遍历时，列表更合适；输入大、只顺序消费或希望流水处理时，生成器更合适。生成器自身就是保存当前位置的一次迭代器，第一次遍历已推进到 `StopIteration`，第二次不会自动重新执行；要重来需重新调用生成器函数。
4. 上下文管理器保证离开 `with` 块时调用退出协议，因此能关闭文件、释放锁或提交/回滚由该对象定义的事务。它不能自动撤销已经发给第三方的邮件、付款或其他块外副作用，也不能证明清理动作本身一定成功；这些失败仍需处理和记录。
5. 标注主要供静态工具和读者使用，普通 Python 调用不会自动按注解验证 JSON 字段。即使类型匹配，数值范围、字段关联、状态顺序仍可能错误。外部数据要做运行时解析，程序行为要由测试和业务不变量验证。
6. 对默认启用 GIL 的 CPython，两个执行纯 Python 字节码的 CPU 密集线程通常不能同时利用两个核心，且有调度开销，所以不是优先方案。答案会随解释器实现、版本、是否为 free-threaded build、工作是否在释放 GIL 的原生扩展中执行而改变；应先固定这些前提再实测。
7. 阻塞 I/O 且库没有异步接口时可先用线程，成本是共享状态同步和线程栈；可拆分的 CPU 计算可用进程，成本是启动、序列化和额外内存；大量原生支持异步的网络等待可用 `asyncio`，成本是所有调用必须合作让出事件循环，并正确处理取消、超时和背压。
8. view 是另一个数组描述对象，但与原数组共享底层数据；copy 拥有独立数据，修改不会互相影响。可查看 `.base`、连续性标志并使用 NumPy 的内存共享检查函数；最可靠的接口还应明确约定是否允许修改，而不是靠调用者猜实现。
9. 至少保持元素类型、形状、步长、对齐和字节序一致；Python 所有者必须活到 C++ 停止使用缓冲区；双方要约定谁可修改、何时同步；错误不能以未捕获 C++ 异常跨过 ABI；多线程调用还要遵守 Python 线程状态和 GIL/自由线程构建的协议。
10. 常规事件循环一次只在其线程中执行一个协程的 Python 代码。阻塞压缩函数 500 ms 时没有 `await` 让出控制，因此同一循环中的计时器、网络读写和其他请求都延后。先用事件循环延迟、trace 和栈采样确认这 500 ms 位于循环线程；再把工作批量移到合适的线程/进程池或可异步/释放 GIL 的实现，并设置有界并发。修复后同时验证吞吐、p99、取消和队列是否受控。

</details>

## 16. 本章小结

- Python 变量是名字与对象的绑定；赋值通常不复制对象。
- 可变性、浅复制和共享内层对象是很多隐藏副作用的来源。
- 容器选择要同时看业务语义、平均/摊还成本和最坏边界。
- 生成器按需推进但通常只能消费一次；`with` 负责退出路径清理。
- 类型标注、运行时校验和测试解决不同问题，不能互相替代。
- GIL 是 CPython 构建与版本相关机制；讨论并行前先固定运行环境。
- 线程、进程和 asyncio 分别适合不同等待与共享模型。
- NumPy/C++/GPU 边界必须明确布局、复制、所有权、同步和失败。

## 一手资料

- [Python 官方教程](https://docs.python.org/3/tutorial/)：容器、module、异常、类与虚拟环境。
- [Python Data Model](https://docs.python.org/3/reference/datamodel.html)：对象、迭代器、上下文管理器与特殊方法的语言语义。
- [Python `typing` 文档](https://docs.python.org/3/library/typing.html)：类型标注与静态检查边界。
- [Python `threading` 文档](https://docs.python.org/3/library/threading.html)、[`multiprocessing` 文档](https://docs.python.org/3/library/multiprocessing.html)与[`asyncio` 文档](https://docs.python.org/3/library/asyncio.html)：三类并发接口及其约束。
- [CPython Free-threading 说明](https://docs.python.org/3/howto/free-threading-python.html)与[C API 线程状态说明](https://docs.python.org/3/c-api/threads.html)：GIL 的版本、构建和扩展边界。
- [NumPy Fundamentals](https://numpy.org/doc/stable/user/basics.html)：数组、广播、索引以及 copy/view 语义。
- [pytest 官方文档](https://docs.pytest.org/en/stable/)：fixture、参数化与测试发现。
- [Python Packaging User Guide](https://packaging.python.org/)：`pyproject.toml`、构建与发布的当前规范入口。
