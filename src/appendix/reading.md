# 推荐阅读 (Recommended Reading)

要成为顶级的 HFT 开发者，仅掌握 Rust 语言是远远不够的。你需要深入理解计算机体系结构、操作系统、网络协议以及金融市场微结构。

## 1. 必读书籍

### 系统编程与性能优化
*   **《Systems Performance: Enterprise and the Cloud》 (Brendan Gregg)**
    *   性能分析的圣经。通过它学会使用 perf, eBPF, FlameGraphs。
*   **《Computer Systems: A Programmer's Perspective》 (CSAPP)**
    *   深入理解计算机底层（流水线、缓存、虚拟内存、链接）。
*   **《Rust for Rustaceans》 (Jon Gjengset)**
    *   进阶 Rust 必读，涵盖了生命周期、协变/逆变、宏、Unsafe 等高级话题。

### 金融与算法交易
*   **《Algorithmic Trading & DMA》 (Barry Johnson)**
    *   全面介绍了直连市场准入（DMA）、订单类型、交易算法和微结构。
*   **《Trading and Exchanges》 (Larry Harris)**
    *   关于市场微结构的经典之作，解释了流动性、价格形成机制。

## 2. 经典论文与博客

*   **[The LMAX Architecture](https://martinfowler.com/articles/lmax.html)** (Martin Fowler)
    *   介绍了 Disruptor 模式和单线程业务逻辑的设计思想。
*   **[Mechanical Sympathy](https://mechanical-sympathy.blogspot.com/)** (Martin Thompson)
    *   Martin Thompson 的博客，关于硬件亲和性、无锁编程、内存屏障的深度文章。
*   **[Ulrich Drepper's "What Every Programmer Should Know About Memory"](https://people.freebsd.org/~lstewart/articles/cpumemory.pdf)**
    *   关于 CPU 缓存、NUMA、内存子系统的终极指南（虽然有点老，但原理未变）。

## 3. 视频资源

*   **Carl Cook: "When a Microsecond Is an Eternity" (CppCon 2017)**
    *   Optiver CTO 的演讲，展示了 C++ 在 HFT 中的极端优化技巧。
*   **Jon Gjengset's YouTube Channel**
    *   深入浅出的 Rust 直播，特别是关于 `Pin`, `Future`, `Unsafe` 的系列。
