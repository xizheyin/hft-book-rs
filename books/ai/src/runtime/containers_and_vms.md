# 容器、用户态内核与微型虚拟机（microVM）：隔离边界之下发生了什么

容器、用户态内核和虚拟机提供不同的内核与硬件边界。本章使用 Linux KVM（Kernel-based Virtual Machine，内核虚拟机接口）、QEMU、virtio、gVisor 与 Firecracker 等公开实现说明共同机制；它们是案例，不是唯一选型。

通用的进程、文件描述符与虚拟地址空间见[进程与文件描述符](../../rust-hft/foundations/processes_fds.html)和[虚拟内存](../../rust-hft/foundations/virtual_memory.html)。容器和 VM 的区别建立在这些基础上，关键新增对象是共享或独立的内核、虚拟设备以及快照一致性。

把宿主机想成一栋公寓。普通容器像共用楼体和物业系统的独立房间；虚拟机像在楼内再建一套有自己物业的小楼；用户态内核则像在房门内增加一层翻译与门卫。三者都能隔开住户，但成本、兼容性和攻击面不同。

## 1. 容器隔离了什么，没有隔离什么

容器通常由多种 Linux 机制组合而成：

- namespace 改变进程“能看见什么”，例如 PID、mount、network、IPC、UTS、user。
- cgroup 规定进程“能用多少”，例如 CPU、内存、I/O 和进程数。
- capability 把 root 权限拆小。
- seccomp 过滤系统调用。
- LSM（Linux Security Modules，Linux 安全模块，例如 SELinux、AppArmor）限制对象访问。
- OCI（Open Container Initiative，开放容器倡议）runtime 按运行时规范创建进程、挂载与 namespace。

最关键的一句是：**容器里的进程仍直接调用宿主机内核。**镜像是文件集合，不是安全边界；Kubernetes namespace 主要组织 API 对象，也不能替代 Linux 运行时隔离。

这不是说容器“不安全”，而是说它的安全性来自宿主内核和整套约束的正确组合。攻击者若利用宿主内核漏洞，影响可能越过容器边界。

## 2. VM 到底多了哪几层

VM 内的应用先调用自己的 guest kernel，再通过虚拟 CPU 和虚拟设备访问宿主资源。常见 KVM 架构中可以先记住三个角色：

| 角色 | 通俗理解 | 典型职责 |
|---|---|---|
| guest | 租客的小楼 | 运行应用和 guest kernel |
| KVM | 内核里的虚拟化执行设施 | 创建 VM/vCPU，借助 CPU 虚拟化扩展运行 guest，处理一部分退出与中断 |
| VMM（Virtual Machine Monitor，虚拟机监控器） | 宿主用户态的管理员 | 配置内存和设备、启动 vCPU、处理需要用户态参与的退出；QEMU、Firecracker 都可承担这一角色 |

microVM 仍然是 VM。“micro”通常表示它刻意减少传统 PC 设备、固件和通用功能，以缩小启动成本及攻击面，并不表示它退化成容器。Firecracker 是使用 KVM、面向 serverless 多租户负载的公开案例。

### 2.1 vCPU 不是一块缩小的实体 CPU

vCPU 是 VM 看到的逻辑处理器。VMM 通过 `/dev/kvm` 创建 VM，再创建 vCPU；常见实现用一个宿主线程驱动一个 vCPU。这个线程仍由宿主调度器调度，所以：

- guest 认为自己有 4 个 vCPU，不等于宿主永久拿出 4 个物理核给它。
- vCPU 线程没有获得宿主 CPU 时间时，guest 指令就不能前进。
- guest 内还有一层调度器，因此系统同时存在“宿主调度 vCPU”和“guest 调度应用线程”两层调度。

不要把 vCPU 解释成纯软件模拟。启用硬件辅助虚拟化时，大量普通 guest 指令直接在物理 CPU 上执行，只是处于受控的 guest 模式。

<details>
<summary><strong>深入：VM entry/exit 与两阶段地址翻译</strong></summary>

### 2.2 一次 VM entry/exit 如何发生

先看最小闭环：

```text
宿主 vCPU 线程
    │ ioctl(KVM_RUN)
    ▼
KVM 准备 guest CPU 状态
    │ VM entry
    ▼
CPU 直接执行 guest 指令
    │ 发生需要虚拟化层处理的事件
    ▼
VM exit
    ├─ KVM 可在内核中处理 ──► 再次进入 guest
    └─ 需 VMM 处理 ─────────► KVM_RUN 返回用户态 ─► VMM 模拟/处理 ─► 再调用 KVM_RUN
```

`VM entry` 是 CPU 从宿主执行环境进入 guest；`VM exit` 是 CPU 因某个受配置控制的事件返回虚拟化层。例如 guest 执行需要虚拟化层处理的敏感操作、访问模拟设备、停机，或遇到异常与中断时，都可能触发退出。具体哪些事件退出、由哪一层处理，取决于架构和配置；事件编号本身不能替代对路径的理解。

有两个高频陷阱：

1. **VM exit 不等于 `KVM_RUN` 每次都返回 VMM。**KVM 可在内核中处理一些退出并重新进入 guest，只有需要用户态参与等情形才把退出原因交给 VMM。
2. **宿主抢占 vCPU 线程不等于 guest 主动做了一次设备 VM exit。**两者都会让 guest 暂停，但证据和优化方向不同。

一次 exit 的开销也没有可背诵的固定纳秒数。状态切换、TLB（Translation Lookaside Buffer，地址翻译缓存）影响、退出原因和用户态设备模拟都会改变成本。正确做法是减少不必要的高频退出并实测，不能声称“VM 每条指令都要陷入 hypervisor”。

## 3. 两阶段地址翻译：guest 地址怎样落到宿主内存

容器进程通常只需理解“进程虚拟地址 → 宿主物理地址”。VM 多了一层“客人以为的物理地址”：

```text
guest 应用产生 GVA（guest virtual address）
          │ guest 页表，由 guest kernel 管理
          ▼
        GPA（guest physical address）
          │ 第二阶段页表，由 KVM/hypervisor 管理
          ▼
        HPA（host physical address）
```

在 x86 上，第二阶段硬件机制常称 Intel EPT（Extended Page Tables，扩展页表）或 AMD NPT（Nested Page Tables，嵌套页表）；其他架构也有对应的 stage-2 翻译。CPU 可以在硬件中组合两阶段页表遍历，并把结果缓存进 TLB，所以正常内存访问不需要每次都退出到 VMM。

VMM 还会把一段自己的宿主虚拟地址空间注册为 guest memory backing。它是软件管理内存时的重要视角，但解释 CPU 最终访问路径时，核心仍是 `GVA → GPA → HPA`，不要把三个概念混在一起。

### 3.1 两种 fault 不是一回事

| 现象 | 谁的映射有问题 | 典型处理者 |
|---|---|---|
| guest page fault | GVA 到 GPA 缺页或权限不符 | guest kernel，和普通 OS 缺页类似 |
| EPT/NPT violation（第二阶段 fault） | GPA 到 HPA 尚未建立、需脏页跟踪或权限不符 | KVM/hypervisor，必要时再让 VMM 参与 |

因此，“guest 出现 page fault”不能自动证明宿主内存不够；“EPT violation 很多”也不能只凭名字断言发生安全违规。要结合 fault 类型、内存压力、缺页来源和工作负载阶段判断。

旧式或不支持第二阶段翻译的方案可维护 shadow page table，把两层关系合成宿主可执行的映射。它需要虚拟化层追踪 guest 页表变化。面试若讨论现代 x86 KVM，先讲 EPT/NPT 即可，再把 shadow paging 作为历史或兼容路径。

</details>

## 4. 虚拟设备：模拟、virtio 与直通

guest 不能直接假设自己独占宿主的网卡和 NVMe（Non-Volatile Memory Express，一种常见的高速存储设备接口）。VMM 必须给它呈现某种设备接口，常见有三种思路：

| 方案 | guest 看到什么 | 优点 | 代价与风险 |
|---|---|---|---|
| 设备模拟 | 一块已知的真实/传统设备 | 旧 OS 可用原生驱动，兼容性强 | 寄存器访问和设备行为模拟较重，可能产生较多退出 |
| virtio 半虚拟化 | 标准化的虚拟设备 | guest 与 VMM 都知道是虚拟环境，可批量交换请求，通常更高效 | guest 需要 virtio 驱动；性能仍取决于 backend、拷贝、批处理和通知 |
| 设备直通 | guest 直接管理物理功能或虚拟功能 | 可减少设备模型参与，性能潜力高 | 需要 IOMMU（Input-Output Memory Management Unit，输入输出内存管理单元）限制设备通过 DMA（Direct Memory Access，直接内存访问）可读写的内存；迁移、共享、重置和运维也更复杂 |

“半虚拟化”不是“半台虚拟机”，而是 guest 驱动主动遵守为虚拟环境设计的接口。virtio 是 OASIS 标准；QEMU 可以在用户态提供 backend，也可配合内核 vhost 或外部 vhost-user backend。

<details>
<summary><strong>深入：virtqueue、虚拟中断以及块/网络数据路径</strong></summary>

### 4.1 virtqueue 如何工作

把 virtqueue 想成 guest 和设备 backend 共同看到的任务传送带。简化后的 split virtqueue 流程是：

1. guest 驱动把数据缓冲区描述符放入队列，并发布“有新请求”。
2. guest 在需要时通知设备，这个通知常被称为 kick。
3. backend 读取描述符，完成网络发送、磁盘读写等工作。
4. backend 把完成项放入 used 区，并在需要时通知 guest。
5. KVM 向 guest 注入虚拟中断，guest 驱动回收请求；也可通过批处理、轮询或通知抑制减少中断。

所以 virtio 的正确表述是“用共享队列和批处理减少高成本设备模拟”，不是“保证零拷贝、零 VM exit、零中断”。是否拷贝、是否退出、由谁处理 backend，均取决于实际数据路径。

### 4.2 一次虚拟中断

以网络接收为例，公开通用路径可抽象为：

```text
物理网卡事件
  → 宿主驱动/backend 收到数据
  → virtio backend 更新完成队列
  → KVM/虚拟中断控制器把中断注入某个 vCPU
  → guest kernel 的 virtio 驱动处理中断或轮询队列
  → guest 网络栈把数据交给应用
```

高吞吐系统通常会合并通知或轮询，因此不能假设“一包必然对应一次物理中断和一次 guest 中断”。中断亲和性若和 vCPU/NUMA 放置错位，还可能引入跨核和跨 NUMA 开销。

### 4.3 块设备数据路径

```text
guest 应用 write/read
  → guest VFS（Virtual File System，虚拟文件系统）、具体文件系统、页缓存
  → guest virtio-blk/virtio-scsi 驱动提交描述符
  → virtio backend（QEMU、vhost-user 等）
  → 宿主文件、块设备或远端存储
  → 完成队列 + 虚拟中断/轮询
  → guest 驱动唤醒应用
```

这条链有两层页缓存、两层队列或远端存储时，“guest 的 `write` 返回”离真正持久化可能很远。排障要分别看 guest 文件系统/队列、backend 和宿主设备，不能只看一个 `iostat`。

### 4.4 网络数据路径

```text
guest 应用
  → guest TCP/IP 栈
  → virtio-net TX virtqueue
  → QEMU/vhost/vhost-user backend
  → tap、宿主网络栈/虚拟交换或物理网卡
  → underlay 网络
```

入站路径大致反向。额外的 NAT、overlay、策略、conntrack 和 service mesh 都可能继续加层。小包吞吐差时要特别看每包固定成本、队列与中断；大包或大流量异常时还要看 MTU、分段卸载、拥塞和拷贝。

</details>

## 5. 用户态内核为什么在中间

gVisor 通过 Sentry 在用户态实现 Linux 风格的系统接口，让大量系统调用不直接进入宿主内核；`runsc` 又保持 OCI 运行时接口。它不等同于 VM，也不只是 syscall allowlist。

代价是兼容性与性能需按负载验证。gVisor 官方生产指南明确提醒文件 I/O 和网络往往受影响较大。编译、包管理、海量小文件和频繁联网正是常见 Agent 负载，因此必须用真实任务测试，而不能只跑一个只隔离单项操作的 CPU microbenchmark（微基准）。

## 6. 选型不是“谁绝对更安全”的排行榜

| 维度 | 普通容器 | 用户态内核 | microVM |
|---|---|---|---|
| 内核边界 | 共享宿主内核 | 多数接口由用户态内核处理 | 独立 guest kernel |
| 启动与密度 | 通常最好 | 居中，依实现而定 | 通常成本更高，可用快照优化 |
| Linux 兼容性 | 高 | 需验证 syscall、文件与网络行为 | guest 支持范围内高 |
| 异构 OS | 很弱 | 主要是 Linux 接口 | 比容器更有潜力，但受 guest、固件和设备模型支持限制 |
| 主要攻击面 | 宿主内核接口 | 用户态内核、剩余宿主接口 | VMM、虚拟设备、KVM 与宿主层 |
| 运维复杂度 | 较低 | 中等 | 镜像、guest kernel、设备与快照更复杂 |
| 适用示例 | 可信内部批任务 | 不可信 Linux 用户代码 | 强内核边界、已受支持的 guest OS、高风险任务 |

实际平台可分层：低风险短任务使用高密度运行时；涉及未知二进制、内核特性或更强租户边界的任务使用 microVM；极高风险操作直接拒绝或要求专用节点。最终还要结合威胁模型、补丁速度、配置和验证，不能只按表格自动做决定。

## 7. 快照：复制的不只是内存

快照像暂停一间已经布置好的房间，再从同一状态继续。它能绕过引导和依赖初始化，但完整的可恢复状态至少涉及：

- vCPU 的通用寄存器、控制寄存器、中断等 CPU 状态。
- guest memory。
- VMM 与虚拟设备状态，包括 virtqueue 的位置和未完成请求。
- 与该时刻匹配的块设备内容，或一套明确的块设备快照协议。
- 运行时、CPU 特性、设备模型和快照格式的兼容性元数据。

Firecracker 的公开文档提供了一个具体例子：创建快照前 microVM 必须处于 `Paused`；microVM 状态和 guest memory 分开保存；块设备 backing file 不包含在 microVM 快照里，需要调用方另行管理。其他 VMM 的接口和快照格式必须查各自文档。

### 7.1 一致快照要先定义“一致”

最容易理解的 stop-the-world 思路是：暂停 vCPU，停止或排空会改变状态的设备路径，在同一逻辑点保存 CPU、内存、设备状态，并协调磁盘快照。真实实现会有更细的并发协议，但不变量相同：**恢复后不能看到互相矛盾的时间点。**

例如内存里记录“事务已提交”，磁盘快照却来自提交前，恢复后应用就可能处于从未真实存在过的混合状态。

还要区分两种承诺：

- crash-consistent：类似突然断电后重启，文件系统或数据库依靠 journal/WAL 恢复。
- application-consistent：快照前还让应用 flush、冻结写入或执行专用 hook，保证业务不变量。

暂停 vCPU 只阻止 guest CPU 继续执行，不自动让数据库完成业务级 flush；保存内存也不自动保存外部对象存储、远端数据库和网络对端状态。

<details>
<summary><strong>深入：dirty-page tracking 与增量迁移为什么不等于一致快照</strong></summary>

### 7.2 dirty-page tracking 只回答“哪些页写过”

KVM 的 dirty log 可为 guest memory slot 返回 bitmap，通常每个 guest page 对应一位。某位为 1，表示跟踪窗口内该页被写脏。它可用于增量快照或迁移：先复制全量内存，之后只复制变化页。

典型 pre-copy 迁移可以这样理解：

1. VM 继续运行，同时复制第一轮内存。
2. 跟踪运行期间又被写脏的页。
3. 重复发送脏页，直到剩余量足够小。
4. 短暂停止 VM，复制最后的脏页及 CPU/设备状态，再在目标端恢复。

如果工作负载每秒写脏的内存比网络来得更快，pre-copy 可能迟迟不收敛，只能限制轮数、增加最终停机时间或换策略。

必须牢记：

- dirty bitmap 不说明页里的数据在业务上是否有效。
- 它不让内存与磁盘自动落在同一时刻。
- 设备 DMA（设备绕过 CPU 逐字节搬运而直接读写内存）是否完整计入脏页跟踪，要看 IOMMU、设备和迁移实现。
- 它也不替代 vCPU、虚拟中断和 virtqueue 状态的保存。

因此，“有 dirty tracking，所以快照一致”是错误答案。

</details>

### 7.3 从模板恢复时必须刷新身份

若快照被当作新实例模板，而不是同一实例的暂停/继续，至少要检查并刷新：

- 实例 ID、machine ID、主机名等身份。
- MAC（Media Access Control，介质访问控制）地址、IP 地址、DHCP（Dynamic Host Configuration Protocol，动态主机配置协议）租约、连接状态等网络身份与旧会话。
- 随机数/熵状态，避免多个克隆产生相同随机序列。
- 短期凭证、令牌、SSH（Secure Shell，安全外壳协议）主机密钥和租户秘密。
- 前一租户的缓存、日志、临时文件和内存残留。

基础镜像、guest kernel、VMM、CPU 特性或设备模型升级时，还需检查兼容矩阵并使不兼容快照失效。恢复失败要有界回退冷启动，避免批量重试形成恢复风暴。

假设冷启动 800 ms、恢复 80 ms，每秒新建 2,000 个沙箱，仅按 Little's Law 估算，启动中的平均并发约为 `2000 × 0.8 = 1600` 与 `2000 × 0.08 = 160`。这是教学数字，不是任何产品性能数据，也没有计入排队和长尾。

## 8. vCPU 超卖、非一致内存访问（NUMA）、绑核与“吵闹邻居”

NUMA（Non-Uniform Memory Access）表示 CPU 访问本地内存通常比访问另一颗处理器附近的远端内存更快；pinning 是把线程绑定到指定 CPU；noisy neighbor 是同机租户争用共享资源，导致别人的延迟或吞吐恶化。三者放在一起，是因为错误放置和未隔离的共享资源都会制造长尾。

### 8.1 超卖为什么提高利用率，也伤害长尾

假设宿主有 64 个可用物理执行单元，却给 VM 总共配置了 128 个持续繁忙的 vCPU，粗略超卖比为 `2:1`。理想平均上，每个 vCPU 最多只能分到约一半 CPU 时间，实际还要扣除宿主、VMM 和 I/O 工作；若大部分 vCPU 经常空闲，超卖又可能显著提高平均利用率。

问题通常先出现在尾延迟：多个 vCPU 同时唤醒后进入宿主 run queue，guest 内某个持锁 vCPU 若暂时没被调度，其他 vCPU 即使正在运行也会等待它。guest 常把这部分感知为 steal time 或调度停顿。

### 8.2 pinning 是隔离工具，不是免费加速按钮

把 vCPU 线程固定到一组 pCPU（物理 CPU 执行单元），可减少迁移、改善缓存局部性，并让延迟更可预测。但错误 pinning 会：

- 把多个热点线程挤在同一个物理核或 SMT（Simultaneous Multithreading，同时多线程）的兄弟逻辑核上。
- 忘记给 VMM、vhost 和宿主中断线程留 CPU。
- 让空闲核心无法接手热点，造成容量搁置。
- 只固定 CPU，却让内存和网卡仍在远端 NUMA node。

因此应同时考虑 vCPU、guest memory、网卡/NVMe 队列及中断的 NUMA 放置，并用真实负载比较 p50/p99、run-queue 等待、远端内存和吞吐。

### 8.3 CPU quota 挡不住所有 noisy neighbor

即使两个 VM 的 CPU 时间隔离得很好，它们仍可能争用 LLC（Last-Level Cache，末级缓存）、内存带宽、NUMA 互连、I/O 队列、网卡、宿主锁和中断处理。noisy neighbor 的本质是共享资源竞争，所以排查时要问“还共享了什么”，而不是看到 cgroup quota 就停止。

资源隔离与安全隔离也不同：microVM 提供更强的内核边界，仍需 CPU、内存、I/O 和网络公平调度；容器配额做得很好，也不等于能安全运行任意恶意内核攻击代码。

## 9. 故障证据：先定位哪一层，再谈优化

以下命令只适用于有权限的 Linux 测试机，生产环境先遵守变更和观测规范：

```bash
# KVM 设备是否存在以及当前账号是否可能访问
test -c /dev/kvm && ls -l /dev/kvm

# CPU 是否向当前系统暴露 Intel VMX 或 AMD SVM 标志
grep -m1 -Eo 'vmx|svm' /proc/cpuinfo

# CPU、NUMA 与虚拟化概览
lscpu

# 查看可能的 VMM/vCPU 线程落在哪个 CPU；名称依实现而异
ps -eLo pid,tid,psr,stat,pcpu,comm | grep -E 'qemu|firecracker'

# 宿主 CPU 是否存在持续等待压力
cat /proc/pressure/cpu
```

看不到 `vmx`/`svm` 不必立刻判定物理 CPU 不支持虚拟化：外层 hypervisor 可能未向嵌套 guest 暴露它。`/dev/kvm` 存在也不代表当前账号有权限，更不证明性能正常。

### 故障 A：VM 内 p99 周期性尖刺

先提出可证伪假设：“vCPU 被宿主抢占或放置不当”。证据链可以是：

1. guest 的 steal time、run-queue 等待或应用调度延迟与尖刺同窗上升。
2. 宿主 CPU PSI（Pressure Stall Information，压力停顿信息）或运行队列在同一时间窗口上升，或同核上有其他繁忙 vCPU。
3. vCPU 迁移频繁，或 vCPU 在一个 NUMA node、内存/设备在另一个 node。
4. 在同负载下做受控降超卖、调整亲和性或 NUMA 放置后，p99 明显恢复。

只有前两项是相关性；最后的受控实验才更接近因果验证。若宿主 CPU 压力不高，就继续查 guest 锁、I/O、暂停和应用 GC（Garbage Collection，垃圾回收）停顿，不要强行归因超卖。

### 故障 B：guest 磁盘很慢，宿主盘却不忙

沿路径逐层看：guest 文件系统/iowait 与 virtio 队列、VMM/vhost backend CPU 和限速、宿主文件页缓存、真正的块设备/远端存储。常见候选包括 backend 线程没得到 CPU、virtqueue 堵塞、每请求固定成本过高或 cgroup I/O throttle。换 virtio 并不能自动排除这些问题。

反之，若宿主设备队列和延迟已经饱和，重点应转向设备容量、写回、I/O 调度或远端存储，而不是继续调 guest 驱动。

### 故障 C：快照恢复成功，应用数据却损坏

“API 返回成功”只证明文件被读取和状态被装载，不证明业务一致。应核对：

- CPU、内存、设备状态和磁盘快照是否来自同一逻辑点。
- 是否在设备队列仍有未完成写入时拍了快照。
- dirty bitmap 的窗口与清零时机是否正确，设备 DMA 是否被跟踪。
- 应用需要 crash-consistent 还是 application-consistent，是否执行了必要 flush/freeze。
- VMM、guest kernel、设备模型、CPU 特性和快照格式是否兼容。

修复方向可能是加强 quiesce 协议、协调块快照、加入版本门禁和恢复后 verifier；不能只把“重试恢复”当修复。

## 10. 面试的 30 秒回答

### 问：vCPU 怎样真正运行 guest 指令？

常见 KVM 架构里，VMM 创建 vCPU，并通常由宿主线程调用 `KVM_RUN`。CPU 通过硬件虚拟化进入 guest，大量普通指令直接执行；遇到按配置需处理的事件会 VM exit。KVM 能处理一部分退出，需设备模型等用户态逻辑时才把原因交给 VMM。vCPU 最终仍受宿主调度，所以超卖和抢占会直接影响 guest 尾延迟。

### 问：EPT/NPT 解决什么问题？

guest 页表先把 guest virtual address 翻译成 guest physical address；EPT/NPT 再把它翻译成 host physical address。硬件可完成组合遍历并缓存，所以正常内存访问不必次次退出。guest page fault 和第二阶段 fault 是不同层的问题，排障时必须分开。

### 问：virtio 为什么通常比传统设备模拟快？

传统模拟要复刻真实设备寄存器和行为，guest 访问可能频繁触发退出与模拟；virtio 让 guest 驱动与 backend 通过共享 virtqueue 批量传递描述符，再用 kick 和完成通知协作，减少每次请求的设备模拟。但它不保证零拷贝或零退出，QEMU、vhost、vhost-user、批处理和轮询方式都会影响结果。

### 问：dirty-page tracking 为什么还不够做一致快照？

dirty bitmap 只告诉我某段时间哪些内存页被写过，便于增量复制。它不保存 vCPU/设备/virtqueue 状态，不让磁盘自动与内存对齐，也不保证应用事务一致。完整方案要定义暂停或迁移协议、设备 quiesce、块快照、版本兼容和恢复后的身份刷新与验证。

### 问：为什么不全部用容器或全部用 VM？

容器密度和兼容性通常更好，但共享宿主内核；VM 用 guest kernel 和硬件虚拟化加强边界并支持异构 OS，不过启动、内存和运维成本更高；用户态内核处于中间位置。我会按代码可信度、所需内核能力、租户风险和 SLO 分级，并用真实 Agent 负载测启动、密度、p99、I/O、故障恢复和安全边界。

## 11. 自测：先答，再看提示

1. guest 执行一次普通加法指令，是否一定 VM exit？为什么？
2. `KVM_RUN` 从用户态返回，和 CPU 发生一次 VM exit 是完全相同的概念吗？
3. 写出 GVA、GPA、HPA 的全称和两段映射的管理者。
4. guest page fault 与 EPT/NPT violation 有何区别？
5. virtqueue 的描述符、kick、used ring 和虚拟中断分别负责什么？
6. 为什么 virtio 不能直接等同于零拷贝？
7. 画出一次 guest 块写入和一次网络发送的跨层路径。
8. dirty bitmap 全为 0，能否证明磁盘与内存一致？
9. pre-copy 在什么工作负载下难以收敛？
10. 64 个 pCPU 承载 128 个持续繁忙 vCPU 时，为什么 p99 可能比平均吞吐更早恶化？
11. pinning 之后还要检查哪些 NUMA 与 I/O 放置？
12. 如何用至少三层证据区分“guest 磁盘慢”来自 guest、backend 还是宿主设备？

核对提示：普通 guest 指令通常可直接执行；KVM 可在内核中处理退出；两阶段翻译是 `GVA → GPA → HPA`；virtio 是共享队列协议而非性能保证；dirty tracking 只记录写过的页；高脏页率会拖累 pre-copy；超卖、远端 NUMA 和共享缓存/I/O 都会制造 noisy neighbor。若只能说出这些提示，却画不出数据路径，还应再练一遍第 2、4、7、8 节。

## 12. 本章速记

- 容器共享宿主内核；VM 有 guest kernel；用户态内核重实现或代理大量系统接口。
- vCPU 常由宿主线程驱动，通过 VM entry/exit 在 guest 与虚拟化层之间切换；不是每条指令都退出。
- VM 地址翻译核心是 `GVA → GPA → HPA`，EPT/NPT 负责第二阶段。
- virtio 用 virtqueue、kick 和完成通知降低传统设备模拟成本，但不承诺零拷贝、零退出。
- 一致快照要保存 CPU、内存和设备状态，并协调磁盘；dirty bitmap 只回答哪些页写过。
- 超卖改善平均利用率，却可能伤害 p99；pinning、NUMA 和共享 I/O 要一起考虑。
- KVM、Firecracker、gVisor 等实现细节不能无条件外推到其他运行时。

## 一手资料

- [Linux KVM API：VM、vCPU、KVM_RUN、dirty log 与中断接口](https://docs.kernel.org/virt/kvm/api.html)
- [Linux KVM x86 MMU 文档](https://docs.kernel.org/virt/kvm/x86/mmu.html)
- [QEMU Device Emulation](https://www.qemu.org/docs/master/system/device-emulation.html)
- [QEMU VirtIO Devices](https://www.qemu.org/docs/master/system/devices/virtio/index.html)
- [OASIS Virtio 1.3 规范](https://docs.oasis-open.org/virtio/virtio/v1.3/virtio-v1.3.html)
- [QEMU Migration 框架](https://www.qemu.org/docs/master/devel/migration/main.html)
- [Firecracker Snapshot Support](https://github.com/firecracker-microvm/firecracker/blob/main/docs/snapshotting/snapshot-support.md)
- [Firecracker Snapshot Data Format Versioning](https://github.com/firecracker-microvm/firecracker/blob/main/docs/snapshotting/versioning.md)
- [Firecracker 官方仓库](https://github.com/firecracker-microvm/firecracker)
- [gVisor 官方架构](https://gvisor.dev/docs/architecture_guide/intro/)
- [gVisor Production Guide](https://gvisor.dev/docs/user_guide/production/)
- [Linux cgroup v2 文档](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
- [OCI Runtime Specification](https://github.com/opencontainers/runtime-spec)
