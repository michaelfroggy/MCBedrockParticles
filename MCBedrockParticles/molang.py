import re
import math
import random

class MoLangMath:
    @staticmethod
    def sin(x): return math.sin(math.radians(x))
    @staticmethod
    def cos(x): return math.cos(math.radians(x))
    @staticmethod
    def tan(x): return math.tan(math.radians(x))
    @staticmethod
    def asin(x): return math.degrees(math.asin(x))
    @staticmethod
    def acos(x): return math.degrees(math.acos(x))
    @staticmethod
    def atan(x): return math.degrees(math.atan(x))
    @staticmethod
    def atan2(y, x): return math.degrees(math.atan2(y, x))
    @staticmethod
    def abs(x): return math.fabs(x)
    @staticmethod
    def max(a, b): return max(a, b)
    @staticmethod
    def min(a, b): return min(a, b)
    @staticmethod
    def clamp(val, min_val, max_val): return max(min_val, min(val, max_val))
    @staticmethod
    def exp(x): return math.exp(x)
    @staticmethod
    def ln(x): return math.log(x)
    @staticmethod
    def pow(x, y): return math.pow(x, y)
    @staticmethod
    def sqrt(x): return math.sqrt(x)
    @staticmethod
    def mod(x, y): return x % y if y != 0 else 0
    @staticmethod
    def pi(): return math.pi
    @staticmethod
    def random(a, b): return random.uniform(a, b)
    @staticmethod
    def random_integer(a, b): return random.randint(int(a), int(b))
    @staticmethod
    def round(x): return round(x)
    @staticmethod
    def trunc(x): return math.trunc(x)
    @staticmethod
    def floor(x): return math.floor(x)
    @staticmethod
    def ceil(x): return math.ceil(x)

MATH_ENV = {
    "math": MoLangMath,
    "Math": MoLangMath
}

# Regex to safely replace variable access
RE_V_VAR = re.compile(r'\bv\.([a-zA-Z0-9_]+)\b')
RE_VARIABLE_VAR = re.compile(r'\bvariable\.([a-zA-Z0-9_]+)\b')
RE_Q_VAR = re.compile(r'\bq\.([a-zA-Z0-9_]+)\b')
RE_QUERY_VAR = re.compile(r'\bquery\.([a-zA-Z0-9_]+)\b')
RE_T_VAR = re.compile(r'\bt\.([a-zA-Z0-9_]+)\b')
RE_TEMP_VAR = re.compile(r'\btemp\.([a-zA-Z0-9_]+)\b')

def _replace_vars(expr):
    # MoLang is case insensitive for variable scopes often, but let's just stick to lowercase mapping.
    expr = RE_V_VAR.sub(r'ctx.get("v", {}).get("\1", 0.0)', expr)
    expr = RE_VARIABLE_VAR.sub(r'ctx.get("variable", {}).get("\1", 0.0)', expr)
    expr = RE_Q_VAR.sub(r'ctx.get("q", {}).get("\1", 0.0)', expr)
    expr = RE_QUERY_VAR.sub(r'ctx.get("q", {}).get("\1", 0.0)', expr)
    expr = RE_T_VAR.sub(r'ctx.get("t", {}).get("\1", 0.0)', expr)
    expr = RE_TEMP_VAR.sub(r'ctx.get("t", {}).get("\1", 0.0)', expr)
    
    # Bedrock sometimes uses ? : for conditionals. Convert to python a if b else c
    # A robust parser would use AST, but for simple a ? b : c we can regex it
    # Pattern: condition ? true_val : false_val
    # This is tricky with nested ?:, so we just replace the simplest ones or fallback to 0.0
    # Actually, let's implement a quick replace for `cond ? A : B` -> `A if cond else B`
    while "?" in expr and ":" in expr:
        # Very naive ? : converter
        match = re.search(r'([^?]+)\?([^:]+):(.*)', expr)
        if match:
            cond = match.group(1)
            t_val = match.group(2)
            f_val = match.group(3)
            expr = f"({t_val}) if ({cond}) else ({f_val})"
        else:
            break
            
    # Also replace logic operators
    expr = expr.replace("&&", " and ")
    expr = expr.replace("||", " or ")
    return expr

def evaluate(expression, ctx=None, default=1.0):
    if ctx is None:
        ctx = {}
        
    if isinstance(expression, (int, float)):
        return float(expression)
        
    if isinstance(expression, str):
        try:
            expr = _replace_vars(expression)
            eval_env = {"ctx": ctx, **MATH_ENV}
            res = eval(expr, {"__builtins__": None}, eval_env)
            return float(res)
        except Exception as e:
            # print(f"MoLang eval error on '{expression}': {e}")
            pass
            
        # Fallback to the old basic parser
        match = re.search(r"[-+]?\d*\.\d+|\d+", expression)
        if match:
            return float(match.group())
            
    return default
