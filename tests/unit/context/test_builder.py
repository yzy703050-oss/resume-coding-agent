from coding_agent.context.builder import ContextBuilder
from coding_agent.context.items import (
    ContextItem,
    ContextPriority,
    ContextSection,
    PreparedContext,
)


def test_builder_only_formats_prepared_context() -> None:
    prepared = PreparedContext(
        items=(
            ContextItem(
                "system",
                ContextSection.MANDATORY,
                "Follow the tools",
                ContextPriority.MANDATORY,
                16,
                "runtime",
                metadata={"role": "system"},
            ),
            ContextItem(
                "history",
                ContextSection.RECENT_HISTORY,
                "read app.py",
                ContextPriority.NORMAL,
                11,
                "episodic",
            ),
        ),
        estimated_size=27,
        omitted_by_section={ContextSection.REPO_MAP: 2},
    )

    messages = ContextBuilder().build(prepared)

    assert messages[0].role == "system"
    assert messages[0].content == "Follow the tools"
    assert "RECENT HISTORY:\nread app.py" in messages[1].content
    assert "repo_map=2" in messages[-1].content
