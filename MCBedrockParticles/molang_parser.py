import re
import math
import random

# Token types
NUMBER = 'NUMBER'
IDENT = 'IDENT'
OP = 'OP'
LPAREN = 'LPAREN'
RPAREN = 'RPAREN'
COMMA = 'COMMA'
EOF = 'EOF'

# Regex for tokenization
TOKEN_REGEX = re.compile(r'''
    (?P<NUMBER>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?) |
    (?P<IDENT>[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*) |
    (?P<OP>&&|\|\||==|!=|<=|>=|<|>|\+|-|\*|/|\?|:) |
    (?P<LPAREN>\() |
    (?P<RPAREN>\)) |
    (?P<COMMA>,) |
    (?P<SKIP>[ \t\r\n]+) |
    (?P<MISMATCH>.)
''', re.VERBOSE)

class MoLangParser:
    def __init__(self):
        self.cache = {}
        
        self.env = {
            'math.pi': math.pi,
            'math.e': math.e,
            'math.abs': abs,
            'math.acos': lambda *args: math.degrees(math.acos(max(-1.0, min(1.0, args[0])))) if args else 0.0,
            'math.asin': lambda *args: math.degrees(math.asin(max(-1.0, min(1.0, args[0])))) if args else 0.0,
            'math.atan': lambda *args: math.degrees(math.atan(args[0])) if args else 0.0,
            'math.atan2': lambda *args: math.degrees(math.atan2(args[0], args[1])) if len(args) > 1 else 0.0,
            'math.ceil': lambda *args: math.ceil(args[0]) if args else 0.0,
            'math.cos': lambda *args: math.cos(math.radians(args[0])) if args else 0.0,
            'math.sin': lambda *args: math.sin(math.radians(args[0])) if args else 0.0,
            'math.tan': lambda *args: math.tan(math.radians(args[0])) if args else 0.0,
            'math.exp': lambda *args: math.exp(args[0]) if args else 0.0,
            'math.floor': lambda *args: math.floor(args[0]) if args else 0.0,
            'math.ln': lambda *args: math.log(args[0]) if args and args[0] > 0 else 0.0,
            'math.log': lambda *args: math.log(args[0]) if args and args[0] > 0 else 0.0,
            'math.max': lambda *args: max(args[0], args[1]) if len(args) > 1 else (args[0] if args else 0.0),
            'math.min': lambda *args: min(args[0], args[1]) if len(args) > 1 else (args[0] if args else 0.0),
            'math.min_angle': lambda *args: (((args[0] + 180) % 360) - 180) if args else 0.0,
            'math.mod': lambda *args: math.fmod(args[0], args[1]) if len(args) > 1 and args[1] != 0 else 0.0,
            'math.fmod': lambda *args: math.fmod(args[0], args[1]) if len(args) > 1 and args[1] != 0 else 0.0,
            'math.pow': lambda *args: math.pow(args[0], args[1]) if len(args) > 1 and (args[0] >= 0 or args[1] == int(args[1])) else 0.0,
            'math.random': lambda *args: random.uniform(args[0], args[1]) if len(args) > 1 else random.uniform(0.0, 1.0),
            'math.random_integer': lambda *args: float(random.randint(int(args[0]), int(args[1]))) if len(args) > 1 else float(random.randint(0, 1)),
            'math.die_roll': lambda *args: float(sum(random.uniform(args[1], args[2]) for _ in range(int(args[0])))) if len(args) > 2 else 0.0,
            'math.die_roll_integer': lambda *args: float(sum(random.randint(int(args[1]), int(args[2])) for _ in range(int(args[0])))) if len(args) > 2 else 0.0,
            'math.round': lambda *args: round(args[0]) if args else 0.0,
            'math.sqrt': lambda *args: math.sqrt(args[0]) if args and args[0] >= 0 else 0.0,
            'math.trunc': lambda *args: math.trunc(args[0]) if args else 0.0,
            'math.clamp': lambda *args: max(args[1], min(args[0], args[2])) if len(args) > 2 else 0.0,
            'math.lerp': lambda *args: args[0] + (args[1] - args[0]) * args[2] if len(args) > 2 else 0.0,
            'math.lerprotate': lambda *args: args[0] + (((args[1] - args[0] + 180) % 360) - 180) * args[2] if len(args) > 2 else 0.0,
            'math.hermite_blend': lambda *args: args[0] * args[0] * (3.0 - 2.0 * args[0]) if args else 0.0,
            'math.sign': lambda *args: (1.0 if args[0] > 0 else (-1.0 if args[0] < 0 else 0.0)) if args else 0.0,
        }

    def tokenize(self, code):
        tokens = []
        for mo in TOKEN_REGEX.finditer(code):
            kind = mo.lastgroup
            value = mo.group()
            if kind == 'SKIP':
                continue
            elif kind == 'MISMATCH':
                # Ignore unknown chars instead of crashing
                continue
            tokens.append((kind, value))
        tokens.append((EOF, ''))
        return tokens

    def parse(self, code):
        if code in self.cache:
            return self.cache[code]
            
        if isinstance(code, (int, float)):
            return lambda context: float(code)
            
        if not isinstance(code, str):
            return lambda context: 0.0

        try:
            val = float(code)
            return lambda context: val
        except ValueError:
            pass

        tokens = self.tokenize(code)
        pos = [0]

        def match(expected_kind=None, expected_value=None):
            kind, value = tokens[pos[0]]
            if expected_kind and kind != expected_kind:
                return False
            if expected_value and value != expected_value:
                return False
            pos[0] += 1
            return True

        def peek(expected_kind=None, expected_value=None):
            kind, value = tokens[pos[0]]
            if expected_kind and kind != expected_kind:
                return False
            if expected_value and value != expected_value:
                return False
            return True
            
        def get():
            kind, value = tokens[pos[0]]
            if kind != EOF:
                pos[0] += 1
            return kind, value

        def parse_primary():
            kind, value = get()
            if kind == NUMBER:
                v = float(value)
                return lambda ctx: v
            elif kind == IDENT:
                name = value.lower()
                if peek(LPAREN):
                    match(LPAREN)
                    args = []
                    if not peek(RPAREN):
                        args.append(parse_expression())
                        while peek(COMMA):
                            match(COMMA)
                            args.append(parse_expression())
                    match(RPAREN)
                    return lambda ctx: self.call_func(ctx, name, [a(ctx) for a in args])
                else:
                    return lambda ctx: self.resolve_ident(ctx, name)
            elif kind == LPAREN:
                node = parse_expression()
                match(RPAREN)
                return node
            elif kind == OP and value == '-':
                node = parse_primary()
                return lambda ctx: -node(ctx)
            elif kind == OP and value == '!':
                node = parse_primary()
                return lambda ctx: 1.0 if not node(ctx) else 0.0
            return lambda ctx: 0.0

        def parse_mul():
            node = parse_primary()
            while peek(OP, '*') or peek(OP, '/'):
                _, op = get()
                right = parse_primary()
                if op == '*':
                    node = (lambda l, r: lambda ctx: l(ctx) * r(ctx))(node, right)
                else:
                    node = (lambda l, r: lambda ctx: l(ctx) / r(ctx) if r(ctx) != 0 else 0.0)(node, right)
            return node

        def parse_add():
            node = parse_mul()
            while peek(OP, '+') or peek(OP, '-'):
                _, op = get()
                right = parse_mul()
                if op == '+':
                    node = (lambda l, r: lambda ctx: l(ctx) + r(ctx))(node, right)
                else:
                    node = (lambda l, r: lambda ctx: l(ctx) - r(ctx))(node, right)
            return node

        def parse_cmp():
            node = parse_add()
            while peek(OP) and tokens[pos[0]][1] in ('<', '<=', '>', '>=', '==', '!='):
                _, op = get()
                right = parse_add()
                if op == '<':
                    node = (lambda l, r: lambda ctx: 1.0 if l(ctx) < r(ctx) else 0.0)(node, right)
                elif op == '<=':
                    node = (lambda l, r: lambda ctx: 1.0 if l(ctx) <= r(ctx) else 0.0)(node, right)
                elif op == '>':
                    node = (lambda l, r: lambda ctx: 1.0 if l(ctx) > r(ctx) else 0.0)(node, right)
                elif op == '>=':
                    node = (lambda l, r: lambda ctx: 1.0 if l(ctx) >= r(ctx) else 0.0)(node, right)
                elif op == '==':
                    node = (lambda l, r: lambda ctx: 1.0 if l(ctx) == r(ctx) else 0.0)(node, right)
                elif op == '!=':
                    node = (lambda l, r: lambda ctx: 1.0 if l(ctx) != r(ctx) else 0.0)(node, right)
            return node

        def parse_and():
            node = parse_cmp()
            while peek(OP, '&&'):
                get()
                right = parse_cmp()
                node = (lambda l, r: lambda ctx: 1.0 if (l(ctx) and r(ctx)) else 0.0)(node, right)
            return node

        def parse_or():
            node = parse_and()
            while peek(OP, '||'):
                get()
                right = parse_and()
                node = (lambda l, r: lambda ctx: 1.0 if (l(ctx) or r(ctx)) else 0.0)(node, right)
            return node

        def parse_ternary():
            node = parse_or()
            if peek(OP, '?'):
                get()
                true_expr = parse_expression()
                if peek(OP, ':'):
                    get()
                    false_expr = parse_expression()
                else:
                    false_expr = lambda ctx: 0.0
                node = (lambda cond, t, f: lambda ctx: t(ctx) if cond(ctx) else f(ctx))(node, true_expr, false_expr)
            return node

        def parse_expression():
            return parse_ternary()

        try:
            ast = parse_expression()
            self.cache[code] = ast
            return ast
        except Exception as e:
            print(f"MoLang Parse Error on '{code}': {e}")
            return lambda ctx: 0.0

    def call_func(self, ctx, name, args):
        if name in self.env and callable(self.env[name]):
            try:
                return float(self.env[name](*args))
            except Exception:
                return 0.0
        return 0.0

    def resolve_ident(self, ctx, name):
        if name in self.env:
            val = self.env[name]
            if callable(val):
                return 0.0
            return float(val)
            
        parts = name.split('.')
        prefix = parts[0]
        if prefix in ('v', 'variable', 'q', 'query', 't', 'temp'):
            if len(parts) > 1:
                c = ctx.get(prefix, {})
                full_name = '.'.join(parts[1:])
                if full_name in c:
                    return float(c[full_name])
                
                val = c
                for p in parts[1:]:
                    if isinstance(val, dict) and p in val:
                        val = val[p]
                    elif hasattr(val, p):
                        val = getattr(val, p)
                    else:
                        return 0.0
                return float(val) if val is not None else 0.0
        return 0.0

    def evaluate(self, code, context=None):
        if context is None:
            context = {'v': {}, 'q': {}, 't': {}}
        ast = self.parse(code)
        try:
            val = ast(context)
            return float(val)
        except Exception:
            return 0.0

_parser = MoLangParser()

def evaluate(code, context=None):
    return _parser.evaluate(code, context)

def execute_statements(code, context):
    if not code:
        return
    if context is None:
        context = {'v': {}, 'q': {}, 't': {}}
    statements = str(code).split(';')
    import re
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        m = re.search(r'(?<![<>=!])=(?!=)', stmt)
        if m:
            left = stmt[:m.start()].strip()
            right = stmt[m.end():].strip()
            val = evaluate(right, context)
            parts = left.split('.')
            if len(parts) >= 2 and parts[0].lower() in ('v', 'variable', 't', 'temp'):
                var_name = '.'.join(parts[1:])
                prefix = 'v' if parts[0].lower() in ('v', 'variable') else 't'
                if prefix not in context:
                    context[prefix] = {}
                context[prefix][var_name] = val
        else:
            evaluate(stmt, context)
