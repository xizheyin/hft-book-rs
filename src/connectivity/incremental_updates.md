# 增量更新与快照 (Incremental Updates & Snapshots)

交易所通常通过两种方式分发数据：
1.  **Incremental (增量)**: 实时推送每一个变化（Add, Modify, Delete, Execute）。UDP 多播，速度极快。
2.  **Snapshot (快照)**: 定期（如每秒）或按需推送当前的完整订单簿状态。TCP 或 UDP，数据量大。

一个健壮的 HFT 系统必须能处理“热加入” (Late Join) 和“丢包恢复” (Gap Recovery)，这就涉及到增量与快照的协同工作。

## 1. 增量消息处理

在 ITCH 或 SBE 协议中，常见的增量消息有：

### 1.1 Add Order (新增)
- **动作**: 在 `orders` 表中插入新订单，在 `levels` 表中对应价格增加数量。
- **注意**: 如果 `Order ID` 已存在，说明这是重复包（A/B 通道），直接忽略。

### 1.2 Order Executed (成交)
- **动作**: 减少订单数量。如果数量减为 0，删除订单。
- **陷阱**: `Executed` 消息只减少数量，不删除订单ID？还是说只有 `Order Delete` 才会删除？
    - 在 ITCH 中，`Order Executed` 只是部分成交。如果完全成交，不需要显式的 `Delete` 消息（或者说数量归零即视为删除）。
    - 但某些协议会发送 `Executed` 后紧跟 `Delete`。必须仔细阅读交易所规范。

### 1.3 Order Cancel / Delete (撤单)
- **Cancel**: 减少数量（部分撤单）。
- **Delete**: 删除整个订单。

### 1.4 Order Replace (改单)
- **动作**: 相当于 `Delete` 旧订单 + `Add` 新订单。
- **优化**: 如果只是改数量（价格不变），且优先级不变，可以直接原地修改，避免哈希表操作。但如果价格变了，必须重新排队（失去了时间优先级）。

## 2. 快照处理 (Snapshot Processing)

当你早上 9:30 启动程序时，或者中间网络断了重连时，你没有全量数据。这时你需要 Snapshot。

### 2.1 状态恢复流程 (Recovery Process)
1.  **Buffer Incremental**: 开始缓存收到的增量数据（此时无法应用，因为缺前置状态）。
2.  **Request Snapshot**: 请求最新的快照。
3.  **Apply Snapshot**: 清空本地订单簿，应用快照。快照通常包含一个 `LastSequenceNumber` (比如 Seq 1000)。
4.  **Replay Buffered**: 从缓存中找出 Seq > 1000 的增量消息，依次应用。
5.  **Go Live**: 追上最新 Seq 后，切回实时处理模式。

### 2.2 循环缓冲区 (Ring Buffer) 的妙用
为了缓存增量消息，我们可以使用之前实现的 `SpscRingBuffer`。

```rust
struct RecoveryManager {
    buffer: RingBuffer<MdMsg, 65536>,
    state: State, // Normal, Recovering
}

impl RecoveryManager {
    fn on_packet(&mut self, msg: MdMsg) {
        match self.state {
            State::Normal => {
                if is_gap(msg.seq) {
                    self.state = State::Recovering;
                    self.buffer.push(msg);
                    request_snapshot();
                } else {
                    process(msg);
                }
            }
            State::Recovering => {
                self.buffer.push(msg);
            }
        }
    }
    
    fn on_snapshot(&mut self, snap: Snapshot) {
        apply_snapshot(snap);
        // Replay
        while let Some(msg) = self.buffer.pop() {
            if msg.seq > snap.last_seq {
                process(msg);
            }
        }
        self.state = State::Normal;
    }
}
```

## 3. 常见陷阱

1.  **Crossed Book (交叉盘)**:
    在恢复过程中，如果逻辑有误，可能会导致你的本地订单簿出现 `Bid > Ask` 的情况。
    **防御**: 每次更新后检查 `BestBid < BestAsk`。如果交叉，说明数据严重错误，必须强制重置。

2.  **Phantom Orders (幽灵订单)**:
    如果你错过了一个 `Delete` 消息，那个订单就会永远留在你的内存里。久而久之，内存泄漏，且订单簿越来越厚。
    **解决**: 
    - 定期对比快照。
    - 交易所通常会在收盘时发送 "System Event" 清空所有订单。

3.  **Seq Number Rollover (序列号回绕)**:
    虽然 `u64` 很大，但某些协议使用 `u32`。注意处理回绕逻辑。

---
下一章：[订单路由系统 (Order Routing)](order_routing.md)
