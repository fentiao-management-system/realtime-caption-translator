from app.ai.memory import ConversationMemory


class FakeClient:
    def __init__(self) -> None:
        self.summarize_calls: list[str] = []

    def summarize(self, content: str) -> str:
        self.summarize_calls.append(content)
        return "这是摘要"


def test_summary_trigger_and_context() -> None:
    mem = ConversationMemory(client=FakeClient(), max_recent_turns=10, summarize_every=5)

    chunk = None
    for i in range(5):
        chunk = mem.add_transcript(f"第{i}句")
    assert chunk is not None and len(chunk) == 5

    # 摘要进行期间，新的识别文本不会再次触发
    assert mem.add_transcript("额外一句") is None

    mem.complete_summary("这是摘要")
    ctx = mem.build_context()
    joined = "\n".join(m["content"] for m in ctx)
    assert "这是摘要" in joined
    assert "额外一句" in joined
    assert "第0句" not in joined  # 已被摘要吸收


def test_qa_kept_in_context() -> None:
    mem = ConversationMemory(client=FakeClient(), max_recent_turns=10, summarize_every=100)
    mem.add_transcript("今天开会讨论进度")
    mem.add_qa("会议结论是什么？", "按计划推进")
    ctx = mem.build_context()
    roles = [m["role"] for m in ctx]
    assert roles.count("assistant") == 1
    assert ctx[-1]["content"] == "按计划推进"


def test_reset_clears_all() -> None:
    mem = ConversationMemory(client=FakeClient())
    mem.add_transcript("一句话")
    mem.add_qa("q", "a")
    mem.reset()
    ctx = mem.build_context()
    assert len(ctx) == 1  # 只剩系统提示


def test_speaker_prefix_in_context() -> None:
    mem = ConversationMemory(client=FakeClient(), max_recent_turns=10, summarize_every=100)
    mem.add_transcript("今天开会讨论进度", "我")
    mem.add_transcript("下周完成第一版测试", "对方")
    joined = "\n".join(m["content"] for m in mem.build_context())
    assert "我：今天开会讨论进度" in joined
    assert "对方：下周完成第一版测试" in joined


def test_recall_finds_older_turns_by_question() -> None:
    mem = ConversationMemory(client=FakeClient(), max_recent_turns=2, summarize_every=100)
    mem.add_transcript("预算审批需要找财务确认", "对方")
    for i in range(6):
        mem.add_transcript(f"闲聊内容第{i}句", "我")
    recalled = mem.recall("预算审批要找谁确认？")
    assert recalled, "应能检索到更早的相关片段"
    assert "预算审批" in recalled[0]

    ctx = mem.build_context("预算审批要找谁确认？")
    joined = "\n".join(m["content"] for m in ctx)
    assert "检索" in joined and "预算审批" in joined
