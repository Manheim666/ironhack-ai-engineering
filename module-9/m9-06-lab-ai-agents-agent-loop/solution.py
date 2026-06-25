"""
Lab 6 | Your First Agent (Google ADK)

We hand the wheel to the model. One ADK agent gets instructions + two tools +
a session, and runs the reason -> act -> observe loop ON ITS OWN: it decides
which tool to call and when it's done. We just design it and read the trace.

The goal needs several steps (look up order, multiply, reason about warranty),
so we see the agent plan and chain tool calls without scripting them.

Run:  python solution.py   (needs GOOGLE_API_KEY; ADK uses GOOGLE_API_KEY)
"""

import asyncio
import json
import os

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")  # <- paste key or export it
MODEL = "gemini-2.5-flash"
APP = "orders_app"
ORDERS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "orders.json")))


# --------------------------------------------------------------------------
# Tools — plain functions; ADK builds the schema from the signature + docstring.
# --------------------------------------------------------------------------
def lookup_order(order_id: str) -> dict:
    """Look up an order by its id.

    Args:
        order_id: the order id, e.g. "A1001".
    Returns:
        A dict with item, price, purchased date and warranty_months, or an
        'error' key if the order does not exist.
    """
    order = ORDERS.get(str(order_id).strip().upper())
    return order or {"error": f"order '{order_id}' not found"}


def calculate(expression: str) -> dict:
    """Evaluate a simple arithmetic expression.

    Args:
        expression: arithmetic only, e.g. "1200 * 2".
    Returns:
        A dict with the numeric 'result', or an 'error' key.
    """
    expr = str(expression)
    if not all(c in "0123456789+-*/(). " for c in expr):
        return {"error": "disallowed characters"}
    try:
        return {"result": eval(expr, {"__builtins__": {}}, {})}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


# --------------------------------------------------------------------------
# The agent
# --------------------------------------------------------------------------
def build_agent():
    from google.adk.agents import Agent

    return Agent(
        name="orders_assistant",
        model=MODEL,
        instruction=(
            "You are a helpful orders assistant. "
            "Use lookup_order to get an order's price, date and warranty. "
            "Use calculate for any arithmetic — never do math in your head. "
            "If lookup_order returns an 'error', tell the user clearly that the "
            "order could not be found and do NOT invent details. "
            "When you have what you need, give a short, direct final answer."
        ),
        tools=[lookup_order, calculate],
    )


async def run_goal(goal):
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    runner = InMemoryRunner(agent=build_agent(), app_name=APP)
    session = await runner.session_service.create_session(app_name=APP, user_id="user-1")

    print("\n" + "=" * 70)
    print(f"GOAL: {goal}\n--- agent trace ---")
    message = types.Content(role="user", parts=[types.Part(text=goal)])

    final = None
    async for event in runner.run_async(
        user_id="user-1", session_id=session.id, new_message=message
    ):
        for part in (event.content.parts if event.content else []):
            if part.function_call:
                fc = part.function_call
                print(f"  [reason->act] call {fc.name}({dict(fc.args)})")
            elif part.function_response:
                fr = part.function_response
                print(f"  [observe]     {fr.name} -> {fr.response}")
            elif part.text and part.text.strip():
                tag = "FINAL" if event.is_final_response() else "think"
                print(f"  [{tag}] {part.text.strip()}")
                if event.is_final_response():
                    final = part.text.strip()
    return final


async def main():
    if not GOOGLE_API_KEY:
        print("GOOGLE_API_KEY empty. ADK needs a Gemini key to run the agent.\n"
              "Set it (export GOOGLE_API_KEY=...) and re-run to see the live trace.")
        return

    # multi-step goal: look up A1001, compute cost of two, reason about warranty
    await run_goal(
        "I'm thinking of buying two more of order A1001. What would those two "
        "cost, and is the original still under warranty?"
    )
    # stretch: a goal it can't complete -> must report honestly, not invent
    await run_goal("How much is order A9999 and what's it covered by?")


if __name__ == "__main__":
    asyncio.run(main())
