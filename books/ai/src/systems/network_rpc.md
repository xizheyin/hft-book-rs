# 网络与 RPC：一个工具请求怎样走到另一台机器

把网络想成寄快递：域名是联系人姓名，IP 地址是城市地址，路由表决定下一站，TCP 负责编号和补寄，TLS 给包裹加密并核验收件人，HTTP/gRPC 则规定包裹里的表格怎样填写。

对 Agent Infra 来说，网络不是“能 ping 通就结束”。一次工具调用可能经过 DNS、负载均衡、代理、服务端队列和数据库；任何一层变慢，用户看到的都只是“Agent 卡住了”。

## 1. 学习优先级

| 优先级 | 必须掌握 | 为什么 |
|---|---|---|
| P0 | IP、路由、ARP/邻居表、TCP、DNS、超时与重试 | 足以解释大多数连接失败和长尾 |
| P0 | TLS、HTTP/1.1、HTTP/2、L4/L7 负载均衡 | Agent 工具和控制面常经过这些层 |
| P0 | `ip`、`ss`、`dig`、`curl`、抓包的证据链 | 面试官关心你怎样证明判断 |
| P1 | gRPC 流式调用、连接池、健康检查 | 用于控制面和长任务事件流设计 |
| P1 | overlay、conntrack、MTU、eBPF | 大规模虚拟网络再深入 |

先做到 P0 能脱稿画图，再学习具体 CNI、Service Mesh 或云厂商产品。产品名不能替代网络原理。

## 2. 端到端概念地图

```mermaid
flowchart LR
    A["Agent 调用工具"] --> B["DNS：名字变 IP"]
    B --> C["路由表：选下一跳"]
    C --> D["ARP/邻居表：找链路层地址"]
    D --> E["TCP：可靠字节流"]
    E --> F["TLS：身份与加密"]
    F --> G["HTTP/1.1、HTTP/2 或 gRPC"]
    G --> H["L4/L7 负载均衡"]
    H --> I["工具服务"]
    I --> J["响应沿连接返回"]
```

这是一张教学图，不表示 DeepSeek 的内部实现。真实系统可能还有 NAT、代理、overlay、网关和多级负载均衡。

## 3. 从域名到第一跳

### 3.1 DNS 先回答“去哪个 IP”

客户端通常先检查本地缓存，再请递归解析器查询。解析器可能从缓存直接返回，也可能沿 DNS 层级继续查询；TTL 控制一条记录可缓存多久。[RFC 1034](https://www.rfc-editor.org/rfc/rfc1034.html)描述域名概念，[RFC 1035](https://www.rfc-editor.org/rfc/rfc1035.html)描述协议和记录格式。

DNS 成功不代表服务健康。它只说明“名字得到一个答案”；答案可能过期、目标端口可能没监听、网络策略也可能拒绝连接。

### 3.2 路由表回答“下一站是谁”

主机拿到目标 IP 后，用路由表选择出口接口和下一跳。可以把路由表理解成按地址前缀匹配的交通指示牌：更具体的路由通常比默认路由优先。

若目标和本机在同一 IPv4 链路，主机会用 ARP 把 IPv4 地址解析为链路层地址；若目标在别的网络，则解析网关的地址。[RFC 826](https://www.rfc-editor.org/rfc/rfc826.html)定义了 ARP。IPv6 使用 Neighbor Discovery，不应把两者混成一个协议。

```bash
ip route get 203.0.113.10
ip neigh show
```

第一条命令展示内核会选择的路由，第二条展示邻居表。文档中的保留示例地址不要换成生产目标随意探测。

## 4. TCP：可靠不等于永不失败

[RFC 9293](https://www.rfc-editor.org/rfc/rfc9293.html)规定 TCP 向应用提供可靠、有序的字节流。关键词是“字节流”：一次 `send` 并不天然对应接收端的一次 `recv`，应用协议必须自己定义消息边界。

建立连接通常经历 SYN、SYN-ACK、ACK。随后序列号帮助排序，确认与重传处理丢包，接收窗口做流量控制，拥塞控制避免发送方把网络压垮。

要区分两个“慢下来”：

- **流量控制**保护接收方，接收方处理不过来会缩小窗口。
- **拥塞控制**保护网络，发送方根据拥塞信号调整发送速率。

TCP 不能保证业务操作只执行一次。连接在服务端写成功后断开，客户端可能只看到超时；是否重试必须由应用层的幂等键、查询接口或事务语义决定。

## 5. TLS：先核验身份，再保护传输

TLS 通常位于 TCP 与应用协议之间。以 TLS 1.3 为例，握手协商算法、建立密钥，并通过证书等机制认证对端；之后应用数据获得机密性和完整性保护，详见 [RFC 8446](https://www.rfc-editor.org/rfc/rfc8446.html)。

常见失败证据包括：证书过期、域名与证书不匹配、信任链不完整、系统时间错误、协议或密码套件不兼容。不要把所有 `handshake failed` 都归因于“网络不通”。

```bash
timeout 5s openssl s_client -brief -connect example.com:443 -servername example.com </dev/null
curl -v --connect-timeout 2 --max-time 5 https://example.com/
```

`-servername` 会发送服务名指示。调试输出可能含请求头和证书信息，不要在共享终端粘贴生产令牌。

## 6. HTTP/1.1、HTTP/2 与 gRPC

HTTP 规定请求和响应语义。[RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html)定义通用语义，[RFC 9112](https://www.rfc-editor.org/rfc/rfc9112.html)描述 HTTP/1.1 的消息格式。

HTTP/1.1 可以复用持久连接，但一个连接上的请求调度容易受前序响应影响。HTTP/2 把消息拆成帧，并允许多个 stream 在同一连接上交错传输，见 [RFC 9113](https://www.rfc-editor.org/rfc/rfc9113.html)。但它仍常运行在一条 TCP 连接上：底层丢包导致 TCP 等待缺失字节时，多条 stream 都可能受影响。

gRPC 把“调用远端函数”包装成明确的服务和消息接口，常使用 Protocol Buffers，并支持 unary、客户端流、服务端流和双向流。协议细节以 [gRPC over HTTP/2](https://github.com/grpc/grpc/blob/master/doc/PROTOCOL-HTTP2.md)的一手规范为准。

Agent Infra 中可以这样选：

- 简单公开 API：HTTP/JSON 易调试、生态广。
- 内部强类型接口：gRPC 便于代码生成和流式传输。
- 长任务事件：流式接口可降低轮询浪费，但必须处理断线续传和背压。

协议选择不能消除超时、重试、版本兼容和鉴权问题。

## 7. L4 与 L7 负载均衡

L4 负载均衡主要依据 IP、端口和传输层连接转发，不必理解具体 HTTP 路径。L7 负载均衡理解应用协议，可以按 Host、路径、方法或请求属性路由。

| 问题 | L4 更自然 | L7 更自然 |
|---|---:|---:|
| 低层 TCP 转发 | 是 | 不一定需要 |
| 按 API 路径分流 | 否 | 是 |
| TLS 终止与应用鉴权 | 通常不做 | 常见 |
| 看懂 gRPC method | 否 | 可以 |

健康检查也有层次。TCP 端口能建立，只能说明进程可能在监听；应用级检查才可能证明依赖和核心路径可用，但过重的健康检查本身会制造负载。

## 8. 超时、重试与一个数字例子

假设一次 Agent 工具调用依次花费：

```text
DNS 10 ms + 建连 20 ms + TLS 30 ms
+ 网关排队 40 ms + 服务执行 300 ms = 400 ms
```

若客户端总超时设为 350 ms，这个正常请求也会失败。若客户端、网关和服务各自最多重试 2 次，最坏情况下并非“多两次”，而可能形成层层放大的尝试数。

更稳妥的做法是：

1. 先定义端到端 deadline，例如 1 秒。
2. 每一跳从剩余预算中分配超时，而不是各自都设 1 秒。
3. 只在错误可重试、仍有预算、操作可安全重复时重试。
4. 设置最大尝试次数、指数退避、随机抖动和全局重试预算。
5. 把 request ID、attempt、剩余 deadline 写进 trace。

`timeout` 是停止等待的决定，不是取消已经发生副作用的证明。

## 9. Linux 上怎样建立证据链

按从便宜到昂贵的顺序观察：

```bash
dig example.com
ip route get 203.0.113.10
ss -tin
curl -sS --connect-timeout 2 --max-time 5 -o /dev/null \
  -w '%{time_namelookup} %{time_connect} %{time_appconnect} %{time_starttransfer}\n' \
  https://example.com/
```

- `dig`：DNS 回答和耗时是否异常。
- `ip route get`：出口、源地址、下一跳是否符合预期。
- `ss -tin`：连接状态、队列和 TCP 内部信息；字段以 [`ss(8)`](https://man7.org/linux/man-pages/man8/ss.8.html)为准。
- `curl -w`：粗分 DNS、TCP、TLS 和首字节时间。

需要抓包时，只在自己有权限的测试环境进行：

```text
# 伪命令：<disposable-test-interface> 必须替换为专用测试接口
sudo timeout 15s tcpdump -i <disposable-test-interface> -c 100 -nn -s 128 \
  'host 203.0.113.10 and tcp port 443'
```

上面故意使用 `text` 而不是可执行的 `bash` 代码块。抓包可能捕获隐私数据，`sudo` 也会扩大影响范围。不要在共享生产主机上无边界抓包；先取得授权，再限定专用接口、地址、端口、包数、时长和文件权限。抓到 TLS 密文也不代表没有元数据泄露。

## 10. 与 Agent Infra 的联系

Agent 的网络负载比普通短 API 更棘手：任务持续时间长、工具种类多、模型可能反复调用、输出大小难预测，还可能执行不可信代码。

平台至少应考虑：

- 每租户、每任务、每工具的出口策略和审计。
- DNS、连接数、带宽、并发与请求次数的配额。
- request ID、task ID、tool call ID 和 attempt 的跨服务传播。
- 长连接断开后的续传位置，而不是从头重复副作用。
- 对内网地址、云元数据服务和控制面的默认拒绝。
- 把超时区分为 DNS、connect、TLS、first byte、idle 和 total。

这些是通用设计原则，不代表 DeepSeek 采用某个特定代理、负载均衡器或网络插件。

## 11. 常见误区

1. **“ping 通就说明服务正常。”** ICMP 可达与 TCP 端口、TLS、应用依赖是不同层。
2. **“TCP 可靠，所以调用恰好执行一次。”** TCP 只保证连接内字节流语义。
3. **“HTTP/2 没有队头阻塞。”** stream 级调度改善了 HTTP 层问题，TCP 丢包仍可能影响整条连接。
4. **“超时后重试总能提高可用性。”** 重试可能重复副作用并放大过载。
5. **“DNS 只有一次查询。”** 缓存、递归解析和多条候选记录都会影响路径。
6. **“L7 一定比 L4 高级。”** 多理解一层也意味着更多成本、状态和故障面。

## 12. 面试怎么答

### 30 秒答案

> 我会把一次工具请求拆成 DNS、路由与邻居解析、TCP 建连、TLS 握手、HTTP/gRPC、负载均衡和服务执行。排障时先用 deadline 与 trace 确定慢在哪一段，再用 `dig`、`ip route`、`ss`、`curl` 和有边界的抓包找证据。TCP 可靠不等于业务恰好一次，所以重试必须结合幂等键、剩余预算、退避和副作用确认。

### 常见追问

- TCP 流量控制和拥塞控制分别保护谁？
- DNS 成功但连接超时，你下一步查什么？
- HTTP/2 多路复用为什么仍可能一起卡住？
- L4 与 L7 负载均衡怎样选择？
- 工具调用超时但可能已付款，怎样恢复？
- 为什么健康检查不能只测试端口？

## 13. 章末自测

1. 从输入 URL 开始，画到服务进程收到请求为止的路径。
2. 解释 ARP 解析的是谁；目标跨网段时为什么通常解析网关。
3. 解释 TCP 为什么不能保留应用消息边界。
4. 分别举一个 DNS、TLS、HTTP 和业务层失败。
5. 为 800 ms 总 deadline 分配各阶段预算，并说明重试条件。
6. 设计一次安全抓包：写出接口、过滤条件、最长时间和数据保管方式。

## 14. 本章小结

- 网络排障要逐层定位，不能把所有错误叫作“网络问题”。
- DNS 找地址，路由选下一跳，TCP 提供可靠字节流，TLS 保护传输，HTTP/gRPC 定义调用。
- L4 与 L7 是不同取舍，不是简单的高低级关系。
- deadline、幂等、退避、抖动和重试预算必须一起设计。
- Agent Infra 还要增加多租户出口控制、审计和长任务恢复。

## 一手资料

- [RFC 9293：TCP](https://www.rfc-editor.org/rfc/rfc9293.html)
- [RFC 1034：DNS 概念](https://www.rfc-editor.org/rfc/rfc1034.html)与 [RFC 1035：协议和记录格式](https://www.rfc-editor.org/rfc/rfc1035.html)
- [RFC 8446：TLS 1.3](https://www.rfc-editor.org/rfc/rfc8446.html)
- [RFC 9110：HTTP 语义](https://www.rfc-editor.org/rfc/rfc9110.html)、[RFC 9112：HTTP/1.1](https://www.rfc-editor.org/rfc/rfc9112.html)与 [RFC 9113：HTTP/2](https://www.rfc-editor.org/rfc/rfc9113.html)
- [`ip-route(8)` 与 `ss(8)`](https://man7.org/linux/man-pages/man8/ip-route.8.html)
