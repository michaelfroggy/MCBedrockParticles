import re
import math
import random

class MoLangError(Exception):
    pass

class Lexer:
    tokens = [
        ('NUMBER', r'\d+(\.\d*)?'),
        ('IDENT', r'[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*'),
        ('OP_EQ', r'=='),
        ('OP_NE', r'!='),
        ('OP_LE', r'<='),
        ('OP_GE', r'>='),
        ('OP_AND', r'&&'),
        ('OP_OR', r'\|\|'),
        ('ASSIGN', r'='),
        ('LT', r'<'),
        ('GT', r'>'),
        ('PLUS', r'\+'),
        ('MINUS', r'-'),
        ('MUL', r'\*'),
        ('DIV', r'/'),
        ('QUESTION', r'\?'),
        ('COLON', r':'),
        ('LPAREN', r'\('),
        ('RPAREN', r'\)'),
        ('COMMA', r','),
        ('SEMI', r';'),
        ('WS', r'\s+'),
    ]

    def __init__(self, code):
        self.code = code
        self.pos = 0
        self.tokens_list = []
        self.tokenize()

    def tokenize(self):
        pattern = '|'.join(f'(?P<{name}>{regex})' for name, regex in self.tokens)
        for match in re.finditer(pattern, self.code):
            kind = match.lastgroup
            val = match.group()
            if kind == 'WS':
                continue
            self.tokens_list.append((kind, val))
        self.tokens_list.append(('EOF', ''))

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def consume(self, expected_kind=None):
        tok = self.tokens[self.pos]
        if expected_kind and tok[0] != expected_kind:
            raise MoLangError(f"Expected {expected_kind}, got {tok[0]} '{tok[1]}'")
        self.pos += 1
        return tok

    def parse(self):
        stmts = []
        while self.peek()[0] != 'EOF':
            if self.peek()[0] == 'IDENT' and self.peek()[1] == 'return':
                self.consume()
                stmts.append(('return', self.parse_expression()))
                if self.peek()[0] == 'SEMI':
                    self.consume()
            else:
                expr = self.parse_expression()
                if self.peek()[0] == 'ASSIGN':
                    self.consume()
                    val = self.parse_expression()
                    stmts.append(('assign', expr, val))
                else:
                    stmts.append(('expr', expr))
                if self.peek()[0] == 'SEMI':
                    self.consume()
                else:
                    break
        return stmts

    def parse_expression(self):
        return self.parse_ternary()

    def parse_ternary(self):
        node = self.parse_logical_or()
        if self.peek()[0] == 'QUESTION':
            self.consume()
            true_expr = self.parse_expression()
            self.consume('COLON')
            false_expr = self.parse_expression()
            return ('ternary', node, true_expr, false_expr)
        return node

    def parse_logical_or(self):
        node = self.parse_logical_and()
        while self.peek()[0] == 'OP_OR':
            op = self.consume()[1]
            node = ('binop', op, node, self.parse_logical_and())
        return node

    def parse_logical_and(self):
        node = self.parse_equality()
        while self.peek()[0] == 'OP_AND':
            op = self.consume()[1]
            node = ('binop', op, node, self.parse_equality())
        return node

    def parse_equality(self):
        node = self.parse_relational()
        while self.peek()[0] in ('OP_EQ', 'OP_NE'):
            op = self.consume()[1]
            node = ('binop', op, node, self.parse_relational())
        return node

    def parse_relational(self):
        node = self.parse_additive()
        while self.peek()[0] in ('LT', 'GT', 'OP_LE', 'OP_GE'):
            op = self.consume()[1]
            node = ('binop', op, node, self.parse_additive())
        return node

    def parse_additive(self):
        node = self.parse_multiplicative()
        while self.peek()[0] in ('PLUS', 'MINUS'):
            op = self.consume()[1]
            node = ('binop', op, node, self.parse_multiplicative())
        return node

    def parse_multiplicative(self):
        node = self.parse_unary()
        while self.peek()[0] in ('MUL', 'DIV'):
            op = self.consume()[1]
            node = ('binop', op, node, self.parse_unary())
        return node

    def parse_unary(self):
        if self.peek()[0] in ('PLUS', 'MINUS'):
            op = self.consume()[1]
            node = self.parse_unary()
            return ('unary', op, node)
        return self.parse_primary()

    def parse_primary(self):
        tok = self.peek()
        if tok[0] == 'NUMBER':
            self.consume()
            return ('number', float(tok[1]))
        elif tok[0] == 'LPAREN':
            self.consume()
            node = self.parse_expression()
            self.consume('RPAREN')
            return node
        elif tok[0] == 'IDENT':
            self.consume()
            ident = tok[1].lower()
            if self.peek()[0] == 'LPAREN':
                self.consume()
                args = []
                if self.peek()[0] != 'RPAREN':
                    args.append(self.parse_expression())
                    while self.peek()[0] == 'COMMA':
                        self.consume()
                        args.append(self.parse_expression())
                self.consume('RPAREN')
                return ('call', ident, args)
            else:
                return ('var', ident)
        else:
            raise MoLangError(f"Unexpected token {tok[0]} '{tok[1]}'")

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
    def random(a=0.0, b=1.0): return random.uniform(a, b)
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
    @staticmethod
    def lerp(start, end, amount): return start + (end - start) * amount

class MoLangCompiler:
    def __init__(self):
        self.cache = {}
        
    def compile(self, code_str):
        if not isinstance(code_str, str):
            return lambda ctx: float(code_str)
            
        code_str = code_str.strip()
        if not code_str:
            return lambda ctx: 0.0
            
        if code_str in self.cache:
            return self.cache[code_str]
            
        try:
            lexer = Lexer(code_str)
            parser = Parser(lexer.tokens_list)
            ast = parser.parse()
            
            py_code = ["def evaluate(ctx):"]
            for stmt in ast:
                py_code.append(self.generate_stmt(stmt, indent="    "))
            if ast and ast[-1][0] == 'expr':
                py_code[-1] = py_code[-1].replace("    _res = ", "    return ")
            else:
                py_code.append("    return 0.0")
                
            code_obj = "\n".join(py_code)
            
            namespace = {"math_env": MoLangMath()}
            exec(code_obj, namespace)
            func = namespace["evaluate"]
            self.cache[code_str] = func
            return func
        except Exception as e:
            def fallback(ctx):
                try: return float(code_str)
                except: return 0.0
            self.cache[code_str] = fallback
            return fallback

    def generate_stmt(self, stmt, indent):
        if stmt[0] == 'return':
            return f"{indent}return float({self.generate_expr(stmt[1])})"
        elif stmt[0] == 'assign':
            var_node = stmt[1]
            if var_node[0] == 'var':
                parts = var_node[1].split('.')
                if len(parts) >= 2:
                    scope = parts[0]
                    name = ".".join(parts[1:])
                    val = self.generate_expr(stmt[2])
                    return f"{indent}if '{scope}' not in ctx: ctx['{scope}'] = {{}}\n{indent}ctx['{scope}']['{name}'] = float({val})"
            return f"{indent}# invalid assign"
        elif stmt[0] == 'expr':
            return f"{indent}_res = float({self.generate_expr(stmt[1])})"

    def generate_expr(self, expr):
        if expr[0] == 'number':
            return str(expr[1])
        elif expr[0] == 'var':
            parts = expr[1].split('.')
            if len(parts) >= 2:
                scope = parts[0]
                name = ".".join(parts[1:])
                return f"float(ctx.get('{scope}', {{}}).get('{name}', 0.0))"
            return f"float(ctx.get('{expr[1]}', 0.0))"
        elif expr[0] == 'call':
            ident = expr[1]
            args = [self.generate_expr(a) for a in expr[2]]
            args_str = ", ".join(args)
            if ident.startswith("math."):
                func_name = ident[5:]
                if hasattr(MoLangMath, func_name):
                    return f"math_env.{func_name}({args_str})"
            elif ident.startswith("q.") or ident.startswith("query."):
                name = ident.split('.', 1)[1]
                return f"float(ctx.get('q', {{}}).get('{name}', lambda *a: 0.0)({args_str}))"
            return "0.0"
        elif expr[0] == 'unary':
            op = expr[1]
            return f"({op}{self.generate_expr(expr[2])})"
        elif expr[0] == 'binop':
            op = expr[1]
            if op == '&&': op = ' and '
            elif op == '||': op = ' or '
            return f"({self.generate_expr(expr[2])} {op} {self.generate_expr(expr[3])})"
        elif expr[0] == 'ternary':
            cond = self.generate_expr(expr[1])
            true_expr = self.generate_expr(expr[2])
            false_expr = self.generate_expr(expr[3])
            return f"({true_expr} if {cond} else {false_expr})"
        return "0.0"

_compiler = MoLangCompiler()

def evaluate(expression, ctx=None, default=0.0):
    if ctx is None:
        ctx = {}
    func = _compiler.compile(expression)
    try:
        return float(func(ctx))
    except Exception as e:
        return default

def execute_statements(code, ctx=None):
    evaluate(code, ctx)

