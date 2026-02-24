# 配置热加载 (Configuration)

在 HFT 中，"重启" 是一个脏词。重启意味着丢失市场数据流、丢失订单队列位置 (Queue Position)、甚至触发交易所的断连惩罚。
然而，市场瞬息万变。我们可能需要调整风控阈值、启用新的策略参数，或者开关某些交易所连接。

本章将介绍如何使用 **ArcSwap (RCU - Read Copy Update)** 模式实现零锁、原子的配置热加载。

## 1. 理论背景：RCU 模式

传统的读写锁 (`RwLock`) 在读多写少场景下依然有开销：
1.  **Cache Line Bouncing**: 每次读取都要修改锁的状态（引用计数），导致缓存行在 CPU 核心间跳跃。
2.  **写者饥饿**: 大量的读者可能导致写者一直拿不到锁。

**RCU (Read-Copy-Update)** 是 Linux 内核中广泛使用的技术：
- **Read**: 读者直接读取指针，无锁，无原子操作。
- **Copy**: 写者先拷贝一份数据，在副本上修改。
- **Update**: 写者原子地替换指针。旧数据在所有读者离开后回收 (Epoch Reclamation)。

在 Rust 中，`arc-swap` 库完美实现了这一模式。

## 2. 核心架构

我们将构建一个全局配置管理器。

```rust
use arc_swap::ArcSwap;
use serde::Deserialize;
use std::sync::Arc;
use std::thread;
use std::time::Duration;

#[derive(Debug, Deserialize, Default)]
pub struct RiskConfig {
    pub max_position: u32,
    pub max_order_size: u32,
    pub kill_switch: bool,
}

#[derive(Debug, Deserialize, Default)]
pub struct StrategyConfig {
    pub spread_threshold: f64,
    pub alpha_beta: f64,
}

#[derive(Debug, Deserialize, Default)]
pub struct AppConfig {
    pub risk: RiskConfig,
    pub strategy: StrategyConfig,
}

// 全局静态配置实例
// lazy_static 或 once_cell 也可以，但在 Rust 1.70+ 用 OnceLock
// 这里为了演示方便，假设它是通过 ArcSwap 包装的
pub struct ConfigManager {
    inner: ArcSwap<AppConfig>,
}
```

## 3. 实现细节

### 3.1 初始化与读取 (Read)

读取路径必须极快。`ArcSwap::load` 返回一个 `Guard`，它类似于 `Arc`，但通常无需原子递增（取决于实现策略）。

```rust
impl ConfigManager {
    pub fn new(initial_config: AppConfig) -> Self {
        Self {
            inner: ArcSwap::from_pointee(initial_config),
        }
    }

    // 热路径 API
    pub fn get(&self) -> Arc<AppConfig> {
        self.inner.load().clone() // 这里 clone 只是增加 Arc 引用计数，开销很小
    }
    
    // 更快的 API: 如果不跨越 await/yield 点，可以直接用 Guard
    pub fn get_ref(&self) -> arc_swap::Guard<Arc<AppConfig>> {
        self.inner.load()
    }
}
```

### 3.2 热加载逻辑 (Update)

后台线程监控配置文件（如 `config.toml`），一旦变化，解析并原子替换。

```rust
use std::fs;

impl ConfigManager {
    pub fn watch_file(self: Arc<Self>, path: &str) {
        let path = path.to_string();
        thread::spawn(move || {
            let mut last_modified = fs::metadata(&path).unwrap().modified().unwrap();
            
            loop {
                thread::sleep(Duration::from_secs(1));
                
                if let Ok(metadata) = fs::metadata(&path) {
                    if let Ok(modified) = metadata.modified() {
                        if modified > last_modified {
                            println!("Config change detected, reloading...");
                            match Self::load_from_file(&path) {
                                Ok(new_config) => {
                                    // 原子替换！
                                    self.inner.store(Arc::new(new_config));
                                    println!("Config reloaded successfully.");
                                    last_modified = modified;
                                }
                                Err(e) => {
                                    eprintln!("Failed to reload config: {}", e);
                                }
                            }
                        }
                    }
                }
            }
        });
    }

    fn load_from_file(path: &str) -> anyhow::Result<AppConfig> {
        let content = fs::read_to_string(path)?;
        let config = toml::from_str(&content)?;
        Ok(config)
    }
}
```

## 4. 常见陷阱 (Pitfalls)

### 4.1 部分更新 (Partial Updates)
**千万不要** 把配置拆成多个 `Atomic` 变量（如 `AtomicU64` max_pos, `AtomicBool` kill_switch）。
这会导致**状态不一致**：线程 A 可能读到了新的 `max_pos` 但旧的 `kill_switch`。
**必须** 整体替换 `AppConfig` 结构体，保证事务性。

### 4.2 验证 (Validation)
在 `store` 之前，必须对 `new_config` 进行严格校验。
例如，如果 `max_order_size` 被误设为 0，可能会导致除以零错误或无法下单。
**Golden Rule**: 只有校验通过的配置才能被 swap 进去。

```rust
fn validate(&self) -> Result<(), String> {
    if self.risk.max_order_size == 0 {
        return Err("max_order_size cannot be 0".into());
    }
    Ok(())
}
```

### 4.3 昂贵的 Drop
旧的 `AppConfig` 会在最后一个读者释放后被 Drop。如果 `AppConfig` 包含这就需要释放大量内存（例如大的 `Vec`），Drop 操作可能会在读者的线程中发生，导致延迟尖峰。
**解决**: 尽量让 Config 保持轻量。如果必须包含重资源，考虑通过 Channel 发送到后台线程去 Drop。

## 5. 延伸阅读

- [arc-swap Crate](https://docs.rs/arc-swap) - Rust 社区的标准 RCU 实现。
- [notify Crate](https://github.com/notify-rs/notify) - 比轮询更高效的文件系统监控。

---
**基础设施篇完结**。接下来我们将进入 **[网络篇 (Network)](../network/README.md)**，探讨如何处理 TCP/UDP 数据流。
