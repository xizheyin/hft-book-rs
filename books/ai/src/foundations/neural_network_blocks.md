# 神经网络的积木：从一层 Linear 到 Transformer Block

想象一座自动化工厂。Linear 层像按配方混合原料，激活函数像只允许某些半成品通过的闸门，Normalization 像把每批原料调回稳定刻度，残差连接则像给深加工流水线保留一条直达通道。Transformer 看起来庞大，本质上仍是这些小积木按固定形状反复堆叠。

> 本章目标：看懂 Linear、激活函数、FFN、Normalization 和残差连接；能计算一个小网络的参数量，并把这些积木与 Attention、MoE 和模型显存联系起来。

## 学习优先级

| 优先级 | 先掌握什么 | 面试要求 |
|---|---|---|
| P1 | Linear、激活函数、FFN、残差、Normalization、参数量 | 能画结构、跟踪形状、解释为什么需要它 |
| P2 | SwiGLU、Pre-Norm/Post-Norm、Dropout、初始化 | 能说明取舍，不必背完整推导 |
| 暂不展开 | 通用逼近定理、矩阵微积分证明 | Agent Infra 面试收益很低 |

## 1. Linear：把一组特征重新混合

一个 Linear（线性）层通常写成：

```text
y = xW + b
```

- `x` 是输入；
- `W` 是模型要学习的权重矩阵；
- `b` 是可选偏置；
- `y` 是输出。

若输入最后一维为 `D_in`，输出最后一维为 `D_out`：

```text
W: [D_in, D_out]
b: [D_out]
参数量 = D_in × D_out + D_out
```

LLM 的输入常是 `[B,T,D]`：Batch 数、Token 数、隐藏维度。Linear 只改变最后一维，不会自动让不同 Token 互相交流：

```text
[B,T,D_in] × [D_in,D_out] → [B,T,D_out]
```

## 2. 为什么不能只堆 Linear

连续两个没有激活函数的 Linear 仍可合并成一个 Linear：

```text
(xW₁)W₂ = x(W₁W₂)
```

层数增加了，表达形式却没有真正变复杂。因此神经网络会在 Linear 之间加入非线性激活函数。

### 2.1 ReLU：最直观的闸门

```text
ReLU(x) = max(0, x)
```

输入 `[-2, 0.5, 3]`，输出 `[0, 0.5, 3]`。它简单高效，但单元若长期落在负区间，梯度可能长期为零。

### 2.2 GELU 与 SiLU：更平滑的闸门

GELU 按输入大小平滑地缩放数值；SiLU 写成：

```text
SiLU(x) = x × sigmoid(x)
```

它们不像 ReLU 那样在零点硬切断；具体模型用哪一种必须查架构配置。

### 2.3 SwiGLU：一条支路给另一条支路开门

```text
gate = SiLU(xW_gate)
value = xW_up
output = (gate ⊙ value)W_down
```

`⊙` 表示逐元素相乘。它比普通两层 FFN 多一条投影支路，所以参数量和 Kernel 布局也不同。确切维度必须看模型配置。

## 3. FFN：每个 Token 自己经过的小网络

Transformer Block 除了 Attention，通常还有 FFN（Feed-Forward Network，前馈网络）：

```text
h → 扩维 Linear → 激活/门控 → 降维 Linear → 输出
```

若隐藏维度从 `D` 扩到 `D_ff`，再降回 `D`，忽略偏置时，普通 FFN 参数量约为：

```text
D × D_ff + D_ff × D = 2DD_ff
```

FFN 对各 Token 位置使用同一套权重，但每个位置独立计算。Attention 像“开会交换信息”，FFN 像“每个人拿着会议结果独立思考”。

## 4. 残差连接：给深层网络留一条直达通道

残差连接常写成：

```text
y = x + F(x)
```

`F(x)` 是 Attention 或 FFN 的变换。若暂时学不到有用变换，网络至少有机会让 `F(x)` 接近 0，使信息沿 `x` 继续向后流动。

残差相加要求形状一致。例如 `[B,T,4096]` 不能直接与 `[B,T,11008]` 相加；FFN 必须先投影回隐藏维度。

## 5. Normalization：把刻度拉回可控制范围

不同层的激活尺度若不断漂移，训练会更难稳定。Normalization 对一组特征做缩放，再乘以可学习系数。

### 5.1 LayerNorm

LayerNorm 对一个 Token 的隐藏特征计算均值和方差，再标准化。直觉上，它同时校正“中心”和“尺度”。

### 5.2 RMSNorm

RMSNorm 使用均方根控制尺度，通常不做减均值步骤：

```text
rms(x) = sqrt(mean(x²) + ε)
y = x / rms(x) × gain
```

`ε` 防止除零。若 `x=[3,4]` 且暂时忽略 `ε` 与 `gain`：

```text
rms = sqrt((9+16)/2) = sqrt(12.5) ≈ 3.536
y ≈ [0.849, 1.131]
```

### 5.3 Pre-Norm 与 Post-Norm

- Pre-Norm：先 Norm，再进入 Attention/FFN，最后做残差相加；
- Post-Norm：先做变换和残差，再 Norm。

二者会影响梯度流和训练稳定性。面试应根据具体模型配置回答，不要把一种顺序说成所有 Transformer 的定律。

## 6. 一个完整可计算的小网络

输入为 `[B=2,T=3,D=4]`，每个 Token 经过普通 FFN：`4 → 8 → 4`。

第一层参数：

```text
W_up: 4×8 = 32
b_up: 8
合计 40
```

第二层参数：

```text
W_down: 8×4 = 32
b_down: 4
合计 36
```

总参数为 `40+36=76`。输出形状仍为 `[2,3,4]`，所以能与原输入做残差相加。

这一遍前向计算共处理 `2×3=6` 个 Token 位置。参数只存一份，不会因 Batch 或 Token 数变成六份；但计算量和中间激活会随位置数增长。

## 7. 参数、激活和显存是三本账

至少分清：

| 对象 | 是什么 | 随什么增长 |
|---|---|---|
| 参数 | `W`、`b` 等学到的数 | 模型层数和维度 |
| 梯度/优化器状态 | 训练更新参数所需状态 | 可训练参数量与优化器 |
| 激活 | 本次前向过程的中间结果 | Batch、序列长度、维度和层数 |
| KV Cache | 推理保存的历史 K/V | 活跃序列数和上下文长度 |

1B 参数若仅以每参数 2 bytes 保存权重，十进制约为 2GB。训练还要保存梯度、优化器状态和激活；推理还要为请求保存 KV Cache。因此“模型文件能放进显存”不代表目标 Batch 或并发一定能跑。

## 8. Encoder、Decoder 与 Decoder-only

Transformer 是积木搭法，不是只有一种网络：

| 架构 | 注意力可见范围 | 常见任务直觉 |
|---|---|---|
| Encoder-only | 通常双向看完整输入 | 理解、分类、表示学习 |
| Decoder-only | 因果遮罩，只看当前位置及过去 | 自回归生成 |
| Encoder–Decoder | Encoder 读输入，Decoder 生成输出并跨注意力读取 Encoder | 输入到输出的序列转换 |

现代生成式 LLM 多采用 Decoder-only，但不能由此推断所有 AI 模型都如此。Agent 调用的模型接口可能隐藏具体结构，Infra 仍应以模型配置和服务契约为准。

## 9. 常见失败与排障

### 9.1 形状接得上，语义却接错

把 `[B,T,D]` 错误转成 `[T,B,D]`，某些维度碰巧相等时程序可能不报错，却把不同请求混在一起。排查时打印每个维度的名字，而不只打印数字。

### 9.2 Loss 变成 NaN

可能原因包括激活/梯度爆炸、学习率过大、低精度溢出、`log(0)` 或 Norm 中除零。建议：

1. 固定最小 Batch；
2. 找到第一个非有限的层，而不是只看最终 Loss；
3. 对比高精度路径；
4. 检查学习率、梯度范数和 Loss Scaling；
5. 确认修复没有用无脑裁剪掩盖坏数据。

### 9.3 训练好、推理差

若模型含 Dropout，训练时会随机关闭部分单元，评测/推理时通常应关闭这种随机失活。还应核对 Tokenizer、Normalization 参数、精度与权重版本。

### 9.4 参数量计算错

常见遗漏是偏置、门控的额外投影、Embedding、输出头和 MoE 的未激活专家。总参数、每 Token 激活参数和实际驻留权重不能混为一谈。

## 10. DeepSeek Agent Infra 面试怎么问

### 30 秒答法

> 神经网络的核心积木是 Linear 加非线性。Transformer 中 Attention 负责 Token 间通信，FFN 负责每个 Token 位置内部变换；残差连接保留直接信息通路，LayerNorm 或 RMSNorm 控制激活尺度。计算参数量要看矩阵形状，运行时还要把权重、训练激活和推理 KV Cache 分开记账。MoE 本质上把单一 FFN 换成路由选择的多个 Expert FFN。

### 常见追问

**为什么多个 Linear 中间必须有非线性？**

没有非线性时，多层 Linear 可合并为一个 Linear，深度没有带来同等的表达能力。

**Attention 和 FFN 各做什么？**

Attention 在 Token 之间汇总上下文；FFN 对每个位置独立做非线性特征变换。

**RMSNorm 与 LayerNorm 有什么直觉差别？**

LayerNorm 通常同时校正均值和尺度；RMSNorm 重点按均方根校正尺度。具体模型用哪种必须查配置。

**为什么参数只占 2GB，训练却可能远超 2GB？**

2GB 只是一份 1B、每参数 2 bytes 的权重，还没有梯度、优化器状态、激活、通信缓冲和临时工作区。

## 11. 章末自测

1. 输入 `[4,128,512]` 经过 `512→2048` 的 Linear，输出形状是什么？若有偏置，参数量是多少？
2. 为什么 FFN 先扩维又降回原维度？为什么必须降回去才能做残差相加？
3. 用一句话分别解释 Attention、FFN、Normalization 和残差。
4. 1B 参数以 2 bytes 保存为什么只是显存预算的起点？
5. 看到 NaN 时，为什么应找“第一个非有限值”而不是直接把所有数裁剪掉？

## 12. 本章小结

- Linear 重新混合最后一维特征；非线性让多层网络不再等价于单层 Linear。
- Attention 负责跨 Token 交流，FFN 负责逐 Token 变换。
- 残差提供直接通路，Normalization 控制激活尺度。
- 参数量由矩阵形状决定；激活、优化器状态与 KV Cache 要另算。
- Encoder、Decoder 和 Decoder-only 是不同积木搭法。
- 形状、数值精度和模型配置都是服务契约的一部分。

## 一手资料

- [Attention Is All You Need：Transformer、残差与 LayerNorm](https://arxiv.org/abs/1706.03762)
- [Deep Residual Learning：残差网络原始论文](https://arxiv.org/abs/1512.03385)
- [Layer Normalization 原始论文](https://arxiv.org/abs/1607.06450)
- [Root Mean Square Layer Normalization 原始论文](https://arxiv.org/abs/1910.07467)
- [GLU Variants Improve Transformer：SwiGLU 等门控 FFN](https://arxiv.org/abs/2002.05202)
- [Deep Learning 教材：前馈网络与正则化](https://www.deeplearningbook.org/)
