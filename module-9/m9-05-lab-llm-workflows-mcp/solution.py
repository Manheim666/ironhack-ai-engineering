"""
Lab 5 | Build the Loop Yourself

The tool-use loop, by hand, in plain Python -- no agent framework, and we do NOT
let the SDK run the loop. We hold the control flow; the model just fills steps.

Two things turn a single call into a small system:
  - short-term MEMORY: one running `messages` list, resent on every model call,
  - a STEP LIMIT: the loop can never run away.

A two-turn conversation proves memory works: turn 2 is only answerable because
turn 1 is still in `messages`.

Run:  python solution.py            (needs GOOGLE_API_KEY)
      python solution.py --selftest (no key: exercises the tools only)
"""

import json
import os
import sys

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")  # <- paste key or export it
CHAT_MODEL = "gemini-2.5-flash"
MAX_STEPS = 5
ORDERS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "orders.json")))


# ----- tools (same two as Lab 4) ------------------------------------------
def lookup_order(order_id: str) -> dict:
    order = ORDERS.get(str(order_id).strip().upper())
    return order or {"error": f"order '{order_id}' not found"}


def calculate(expression: str) -> dict:
    expr = str(expression)
    if not all(c in "0123456789+-*/(). " for c in expr):
        return {"error": "disallowed characters"}
    try:
        return {"result": eval(expr, {"__builtins__": {}}, {})}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


TOOLS = {"lookup_order": lookup_order, "calculate": calculate}


def dispatch(name, args):
    if name not in TOOLS:
        return {"error": f"unknown tool '{name}'"}
    return TOOLS[name](**args)


def tool_decls():
    from google.genai import types

    return types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="lookup_order",
            description="Look up an order id; returns item, price, purchased, warranty_months.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"order_id": types.Schema(type=types.Type.STRING)},
                required=["order_id"]),
        ),
        types.FunctionDeclaration(
            name="calculate",
            description="Evaluate a simple arithmetic expression; returns the number.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"expression": types.Schema(type=types.Type.STRING)},
                required=["expression"]),
        ),
    ])


# --------------------------------------------------------------------------
# The agent: ONE persistent `messages` list = short-term memory.
# --------------------------------------------------------------------------
class HandRolledAgent:
    def __init__(self):
        from google import genai
        from google.genai import types

        self.types = types
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.config = types.GenerateContentConfig(
            tools=[tool_decls()],
            # SDK auto-loop OFF -- WE drive the loop:
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        self.messages = []  # <-- short-term memory, never cleared between turns

    def ask(self, user_text):
        types = self.types
        self.messages.append(types.Content(role="user", parts=[types.Part(text=user_text)]))
        print(f"\nUSER: {user_text}")

        for step in range(1, MAX_STEPS + 1):
            resp = self.client.models.generate_content(
                model=CHAT_MODEL, contents=self.messages, config=self.config
            )
            model_turn = resp.candidates[0].content
            self.messages.append(model_turn)  # append model reply to memory

            calls = [p.function_call for p in model_turn.parts if p.function_call]
            if not calls:
                print(f"  step {step}: final answer")
                print(f"ASSISTANT: {resp.text}")
                return resp.text

            for call in calls:
                args = dict(call.args)
                result = dispatch(call.name, args)
                print(f"  step {step}: tool {call.name}({args}) -> {result}")
                self.messages.append(types.Content(
                    role="user",
                    parts=[types.Part(function_response=types.FunctionResponse(
                        name=call.name, response={"result": result}))]))

        # step limit hit -> stop cleanly, do not loop forever
        print(f"  reached step limit ({MAX_STEPS})")
        return "Sorry, I couldn't finish that in time."


def selftest():
    print("Tool self-test (no model / no key):")
    print(" lookup_order('A1001') ->", lookup_order("A1001"))
    print(" calculate('1200 * 3') ->", calculate("1200 * 3"))
    print("\nThe two-turn memory demo needs GOOGLE_API_KEY -- set it and re-run.")


def main():
    if not GOOGLE_API_KEY or "--selftest" in sys.argv:
        if not GOOGLE_API_KEY:
            print("GOOGLE_API_KEY empty -> self-test only.\n")
        selftest()
        return

    agent = HandRolledAgent()
    # Turn 1 establishes context in `messages`.
    agent.ask("What did order A1001 cost?")
    # Turn 2 has NO order id -> only answerable because turn 1 is still in memory.
    agent.ask("And what about three of them?")
    print(f"\n(messages now holds {len(agent.messages)} entries — that is the memory)")


if __name__ == "__main__":
    main()


# ==========================================================================
# Optional stretch — MCP note (requirements.txt includes `mcp`)
# --------------------------------------------------------------------------
# To use an MCP tool instead of a hand-written function you would: start (or
# connect to) an existing MCP server, list_tools() over the standard MCP
# protocol, and in the loop above replace dispatch() with an MCP call_tool(name,
# args). The DIFFERENCE: a hand-wired function is bound in code (you import it and
# know its signature); an MCP tool is discovered at runtime over a STANDARD
# interface (JSON-RPC), so the same loop can call any MCP server's tools without
# importing its code — tools become pluggable instead of hard-coded.
