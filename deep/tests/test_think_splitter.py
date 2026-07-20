"""Unit tests for the <think> tag splitter (handles tags split across chunks)."""

from radassistant_deep.inprocess import _ThinkSplitter


def drain(pieces):
    return [(k, v) for k, v in pieces]


def run(deltas):
    s = _ThinkSplitter()
    out = []
    for d in deltas:
        out += s.feed(d)
    out += s.flush()
    return out


def joined(out, kind):
    return "".join(v for k, v in out if k == kind)


def test_whole_message_one_chunk():
    out = run(["<think>reason here</think>final answer"])
    assert joined(out, "thinking") == "reason here"
    assert joined(out, "answer") == "final answer"


def test_tag_split_across_chunks():
    # tags arrive char-fragmented, as in token streaming
    deltas = ["<th", "ink>plan", " the ", "work</thi", "nk>", "the ", "answer"]
    out = run(deltas)
    assert joined(out, "thinking") == "plan the work"
    assert joined(out, "answer") == "the answer"


def test_no_tags_is_all_answer():
    out = run(["just ", "a plain ", "answer"])
    assert joined(out, "answer") == "just a plain answer"
    assert joined(out, "thinking") == ""


def test_answer_before_and_after_think():
    out = run(["prefix <think>mid</think> suffix"])
    assert joined(out, "answer") == "prefix  suffix"
    assert joined(out, "thinking") == "mid"


def test_unclosed_think_flushes_as_thinking():
    out = run(["<think>still thinking when the stream ended"])
    assert joined(out, "thinking") == "still thinking when the stream ended"
    assert joined(out, "answer") == ""
