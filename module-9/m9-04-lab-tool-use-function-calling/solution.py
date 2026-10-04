import json
import os
import sys

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")  # <- paste key or export it
CHAT_MODEL = "gemini-2.5-flash"
ORDERS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "orders.json")))



def lookup_order(order_id: str) -> dict:
    order = ORDERS.get(str(order_id).strip().upper())
    if not order:
        return {"error": f"order '{order_id}' not found"}
    return order


def calculate(expression: str) -> dict:
    expr = str(expression)
    if not all(c in "0123456789+-*/(). " for c in expr):
        return {"error": "expression contains disallowed characters"}
    try:
        return {"result": eval(expr, {"__builtins__": {}}, {})} 
    except Exception as e:  # noqa: BLE001
        return {"error": f"could not evaluate: {e}"}


TOOLS = {"lookup_order": lookup_order, "calculate": calculate}


def dispatch(name, args):
    if name not in TOOLS:
        return {"error": f"unknown tool '{name}'"}
    if name == "lookup_order" and "order_id" not in args:
        return {"error": "missing argument order_id"}
    if name == "calculate" and "expression" not in args:
        return {"error": "missing argument expression"}
    return TOOLS[name](**args)


def tool_config():
    from google.genai import types

    lookup_decl = types.FunctionDeclaration(
        name="lookup_order",
        description="Look up an order by id; returns item, price, purchased date, warranty_months.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={"order_id": types.Schema(type=types.Type.STRING,
                                                 description="order id e.g. A1001")},
            required=["order_id"],
        ),
    )
    calc_decl = types.FunctionDeclaration(
        name="calculate",
        description="Evaluate a simple arithmetic expression like '1200 * 3' and return the number.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={"expression": types.Schema(type=types.Type.STRING,
                                                   description="arithmetic expression")},
            required=["expression"],
        ),
    )
    return types.Tool(function_declarations=[lookup_decl, calc_decl])


def run(question, max_steps=6):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GOOGLE_API_KEY)
    config = types.GenerateContentConfig(
        tools=[tool_config()],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    contents = [types.Content(role="user", parts=[types.Part(text=question)])]

    print(f"\nUSER: {question}")
    for step in range(1, max_steps + 1):
        resp = client.models.generate_content(
            model=CHAT_MODEL, contents=contents, config=config
        )
        part_list = resp.candidates[0].content.parts
        contents.append(resp.candidates[0].content) 

        calls = [p.function_call for p in part_list if p.function_call]
        if not calls:
            print(f"FINAL: {resp.text}")
            return resp.text

        for call in calls:
            args = dict(call.args)
            print(f"  [step {step}] model -> tool {call.name}({args})")
            result = dispatch(call.name, args)
            print(f"            our code -> {result}")
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(function_response=types.FunctionResponse(
                        name=call.name, response={"result": result}))],
                )
            )
    print("STOP: hit step limit without a final answer")
    return None


def selftest():
    print("Tool self-test (no model / no key):")
    print(" lookup_order('A1001') ->", lookup_order("A1001"))
    print(" lookup_order('A9999') ->", lookup_order("A9999"))  
    price = lookup_order("A1001")["price"]
    print(f" calculate('{price} * 3') ->", calculate(f"{price} * 3"))
    print(" calculate('2 ** 99 ; import os') ->", calculate("2 ** 99 ; import os"))  # rejected


def main():
    if "--selftest" in sys.argv or not GOOGLE_API_KEY:
        if not GOOGLE_API_KEY:
            print("GOOGLE_API_KEY empty -> running tool self-test only. "
                  "Set the key to run the real model loop.\n")
        selftest()
        return

    run("For order A1001, what would the total be if I bought three of them?")
    run("What can you help me with?")
    run("How much was order A9999?")


if __name__ == "__main__":
    main()
