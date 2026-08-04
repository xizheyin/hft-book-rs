# Summary

- [首页：DeepSeek AI Agent Infra 面试宝典](README.md)
- [官方岗位要求与知识边界](orientation/role_map.md)
- [候选人能力矩阵与面试定位](orientation/candidate_strategy.md)

# 第一部分：AI 与学习基础

- [AI、机器学习、深度学习与 LLM](foundations/ai_ml_llm.md)
- [最小数学直觉：向量、概率、梯度与损失](foundations/math_and_learning.md)
- [数据、泛化、泄漏与分布漂移](foundations/data_and_generalization.md)

# 第二部分：Transformer、DeepSeek 与 LLM 推理

- [Transformer：Token 如何交换信息](llm/transformer.md)
- [自回归生成与采样](llm/generation.md)
- [DeepSeek 架构：MoE、MLA 与 MTP](llm/deepseek_architecture.md)
- [预训练、SFT、偏好对齐与强化学习](llm/training_and_alignment.md)
- [推理系统：Prefill、Decode 与 KV Cache](llm/inference.md)

# 第三部分：Model + Harness = Agent

- [从模型到 Agent：Harness 到底做什么](agent/model_plus_harness.md)
- [Tool Use、Skills 与 MCP](agent/tool_use_and_mcp.md)
- [Context Engineering 与 Memory](agent/context_and_memory.md)
- [Reasoning、Planning 与执行](agent/reasoning_and_planning.md)
- [Subagent 与 Multi-Agent](agent/subagent_multiagent.md)
- [可恢复长任务：状态、幂等与 Checkpoint](agent/durable_execution.md)
- [Agent 评测、轨迹归因与 RL 闭环](agent/evaluation_and_rl.md)
- [检索、RAG、排序与失败归因](agent/retrieval.md)

# 第四部分：DSec 类沙箱运行时

- [一次文件写入：从 write 到真正落盘](runtime/file_write_path.md)
- [Agent 沙箱威胁模型](runtime/sandbox_threat_model.md)
- [容器、用户态内核与 microVM](runtime/containers_and_vms.md)
- [沙箱生命周期与调度](runtime/lifecycle_and_scheduling.md)
- [根文件系统、临时块设备、共享卷与制品](runtime/storage.md)
- [超大规模虚拟网络](runtime/virtual_network.md)
- [控制面与数据面](runtime/control_plane.md)

# 第五部分：分布式平台、观测与安全

- [分布式系统取舍](platform/distributed_systems.md)
- [Agent 可观测性](platform/observability.md)
- [可靠性、SLO 与事故响应](platform/reliability.md)
- [压测与容量规划](platform/performance_capacity.md)
- [能力票据、秘密、供应链与审计](platform/security.md)

# 第六部分：面试实战

- [个性化简历追问与 STAR 故事](interview/resume_drill.md)
- [DSec/Coding Agent 沙箱系统设计](interview/system_design.md)
- [高频问题库：基础、追问、故障与行为题](interview/question_bank.md)
- [14 天、7 天与最后 24 小时冲刺计划](interview/study_plan.md)

# 附录

- [AI Agent Infra 术语表](appendix/glossary.md)
- [资料来源与核验说明](appendix/sources.md)
