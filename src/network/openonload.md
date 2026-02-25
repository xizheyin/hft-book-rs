# Solarflare OpenOnload & ef_vi

在 HFT 领域，Solarflare（现已被 AMD 收购）的网卡是事实上的标准硬件。OpenOnload 是其提供的用户态网络栈，允许应用程序绕过内核直接访问网卡硬件。

## 1. 两种加速模式

### 1.1 透明加速 (Transparent Mode)
这是最简单的使用方式。通过 `LD_PRELOAD` 预加载 Onload 库，可以将标准的 BSD Socket API 调用拦截并重定向到用户态网络栈。

```bash
# 无需修改一行代码
onload --profile=latency ./my_hft_app
```
*   **优点**: 兼容性好，无需改代码。
*   **缺点**: 仍然模拟了 Socket 语义，存在一定的开销。延迟约 1-2µs。

### 1.2 ef_vi (EtherFabric Virtual Interface)
这是 Solarflare 提供的底层 API，类似于 DPDK 和 AF_XDP，但专门针对 Solarflare 硬件进行了极致优化。它允许程序直接操作网卡的收发队列。

*   **优点**: 极致低延迟 (< 1µs)，硬件级过滤。
*   **缺点**: API 复杂，绑定特定硬件。

## 2. Rust 与 ef_vi 实战

要在 Rust 中使用 `ef_vi`，我们需要链接 `libciul` 库。

### 2.1 核心概念
*   **Protection Domain (PD)**: 资源容器，隔离不同进程的资源。
*   **Virtual Interface (VI)**: 包含 RX 环、TX 环和 Event 队列。
*   **Memory Registration**: 必须将 DMA 内存注册到网卡，物理地址固化。

### 2.2 初始化流程

```rust
use std::ffi::c_void;

// 假设我们已经有了 FFI 绑定
// extern "C" { fn ef_driver_open(...) -> c_int; }

struct EfviContext {
    pd: *mut ef_pd,
    vi: *mut ef_vi,
    mem: *mut c_void,
}

impl EfviContext {
    pub fn new(interface: &str) -> Self {
        unsafe {
            // 1. 打开驱动句柄
            let mut driver_handle = 0;
            ef_driver_open(&mut driver_handle);
            
            // 2. 分配 Protection Domain
            let mut pd = std::ptr::null_mut();
            ef_pd_alloc(&mut pd, driver_handle, interface.as_ptr(), ...);
            
            // 3. 分配 Virtual Interface
            let mut vi = std::ptr::null_mut();
            ef_vi_alloc_from_pd(&mut vi, driver_handle, &mut pd, ...);
            
            // 4. 注册 DMA 内存 (用于存放数据包)
            // 内存必须页对齐且锁定 (mlock)
            let mem = aligned_alloc(4096, 2 * 1024 * 1024);
            ef_memreg_alloc(&mut memreg, driver_handle, &mut pd, driver_handle, mem, ...);
        }
        // ...
    }
}
```

### 2.3 极速轮询 (Event Loop)

`ef_vi` 的核心是事件队列 (Event Queue)。所有的数据包到达、发送完成都会产生事件。

```rust
pub fn run_loop(ctx: &mut EfviContext) {
    let mut evs = [ef_event::default(); 32];
    
    loop {
        // 轮询事件队列
        let n_ev = unsafe {
            ef_eventq_poll(ctx.vi, evs.as_mut_ptr(), 32)
        };
        
        for i in 0..n_ev {
            let ev = evs[i];
            
            // 检查事件类型
            if EF_EVENT_TYPE_RX(ev) {
                // 收到数据包
                let pkt_ptr = ctx.get_pkt_ptr(EF_EVENT_RX_DMA_ADDR(ev));
                process_packet(pkt_ptr);
                
                // 重新回填 RX Descriptor，以便网卡再次使用该缓冲区
                ef_vi_receive_post(ctx.vi, ...);
            } else if EF_EVENT_TYPE_TX(ev) {
                // 发送完成
            }
        }
    }
}
```

## 3. 硬件过滤器 (Hardware Filters)

`ef_vi` 允许直接在网卡硬件上设置过滤器，只有匹配的流量才会到达你的 VI。这对于过滤无关的市场数据非常有用。

```rust
// 仅接收 UDP 目标端口 12345 的数据
let filter_spec = ef_filter_spec::udp(12345);
unsafe {
    ef_vi_filter_add(ctx.vi, driver_handle, &filter_spec, ...);
}
```

## 4. 总结

如果你的生产环境全是 Solarflare 网卡，且追求极致的纳秒级优化，**ef_vi 是不二之选**。它的抽象层级比 DPDK 更低，路径更短。

但如果需要跨硬件兼容（如 Mellanox），则应选择 DPDK 或 AF_XDP。
