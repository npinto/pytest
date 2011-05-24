"""
support for presented detailed information in failing assertions.
"""
import py
import imp
import marshal
import struct
import sys
from _pytest.monkeypatch import monkeypatch

try:
    from _pytest.assertrewrite import rewrite_asserts
except ImportError:
    rewrite_asserts = None
else:
    import ast

def pytest_addoption(parser):
    group = parser.getgroup("debugconfig")
    group._addoption('--no-assert', action="store_true", default=False,
        dest="noassert",
        help="disable python assert expression reinterpretation."),

def pytest_configure(config):
    global rewrite_asserts
    # The _reprcompare attribute on the py.code module is used by
    # py._code._assertionnew to detect this plugin was loaded and in
    # turn call the hooks defined here as part of the
    # DebugInterpreter.
    m = monkeypatch()
    config._cleanup.append(m.undo)
    warn_about_missing_assertion()
    if not config.getvalue("noassert") and not config.getvalue("nomagic"):
        def callbinrepr(op, left, right):
            hook_result = config.hook.pytest_assertrepr_compare(
                config=config, op=op, left=left, right=right)
            for new_expl in hook_result:
                if new_expl:
                    return '\n~'.join(new_expl)
        m.setattr(py.builtin.builtins,
                  'AssertionError', py.code._AssertionError)
        m.setattr(py.code, '_reprcompare', callbinrepr)
    else:
        rewrite_asserts = None

def _write_pyc(co, source_path):
    if hasattr(imp, "cache_from_source"):
        # Handle PEP 3147 pycs.
        pyc = py.path(imp.cache_from_source(source_math))
        pyc.dirname.ensure(dir=True)
    else:
        pyc = source_path + "c"
    mtime = int(source_path.mtime())
    fp = pyc.open("wb")
    try:
        fp.write(imp.get_magic())
        fp.write(struct.pack("<l", mtime))
        marshal.dump(co, fp)
    finally:
        fp.close()
    return pyc

def pytest_pycollect_before_module_import(mod):
    if rewrite_asserts is None:
        return
    # Some deep magic: load the source, rewrite the asserts, and write a
    # fake pyc, so that it'll be loaded further down this function.
    source = mod.fspath.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Let this pop up again in the real import.
        return
    rewrite_asserts(tree)
    try:
        co = compile(tree, str(mod.fspath), "exec")
    except SyntaxError:
        # It's possible that this error is from some bug in the assertion
        # rewriting, but I don't know of a fast way to tell.
        return
    mod._pyc = _write_pyc(co, mod.fspath)

def pytest_pycollect_after_module_import(mod):
    if rewrite_asserts is None or not hasattr(mod, "_pyc"):
        return
    # Remove our tweaked pyc to avoid subtle bugs.
    try:
        mod._pyc.remove()
    except py.error.ENOENT:
        pass

def warn_about_missing_assertion():
    try:
        assert False
    except AssertionError:
        pass
    else:
        sys.stderr.write("WARNING: failing tests may report as passing because "
        "assertions are turned off!  (are you using python -O?)\n")

# Provide basestring in python3
try:
    basestring = basestring
except NameError:
    basestring = str


def pytest_assertrepr_compare(op, left, right):
    """return specialised explanations for some operators/operands"""
    width = 80 - 15 - len(op) - 2 # 15 chars indentation, 1 space around op
    left_repr = py.io.saferepr(left, maxsize=int(width/2))
    right_repr = py.io.saferepr(right, maxsize=width-len(left_repr))
    summary = '%s %s %s' % (left_repr, op, right_repr)

    issequence = lambda x: isinstance(x, (list, tuple))
    istext = lambda x: isinstance(x, basestring)
    isdict = lambda x: isinstance(x, dict)
    isset = lambda x: isinstance(x, set)

    explanation = None
    try:
        if op == '==':
            if istext(left) and istext(right):
                explanation = _diff_text(left, right)
            elif issequence(left) and issequence(right):
                explanation = _compare_eq_sequence(left, right)
            elif isset(left) and isset(right):
                explanation = _compare_eq_set(left, right)
            elif isdict(left) and isdict(right):
                explanation = _diff_text(py.std.pprint.pformat(left),
                                         py.std.pprint.pformat(right))
        elif op == 'not in':
            if istext(left) and istext(right):
                explanation = _notin_text(left, right)
    except py.builtin._sysex:
        raise
    except:
        excinfo = py.code.ExceptionInfo()
        explanation = ['(pytest_assertion plugin: representation of '
            'details failed. Probably an object has a faulty __repr__.)',
            str(excinfo)
            ]


    if not explanation:
        return None

    # Don't include pageloads of data, should be configurable
    if len(''.join(explanation)) > 80*8:
        explanation = ['Detailed information too verbose, truncated']

    return [summary] + explanation


def _diff_text(left, right):
    """Return the explanation for the diff between text

    This will skip leading and trailing characters which are
    identical to keep the diff minimal.
    """
    explanation = []
    i = 0 # just in case left or right has zero length
    for i in range(min(len(left), len(right))):
        if left[i] != right[i]:
            break
    if i > 42:
        i -= 10                 # Provide some context
        explanation = ['Skipping %s identical '
                       'leading characters in diff' % i]
        left = left[i:]
        right = right[i:]
    if len(left) == len(right):
        for i in range(len(left)):
            if left[-i] != right[-i]:
                break
        if i > 42:
            i -= 10     # Provide some context
            explanation += ['Skipping %s identical '
                            'trailing characters in diff' % i]
            left = left[:-i]
            right = right[:-i]
    explanation += [line.strip('\n')
                    for line in py.std.difflib.ndiff(left.splitlines(),
                                                     right.splitlines())]
    return explanation


def _compare_eq_sequence(left, right):
    explanation = []
    for i in range(min(len(left), len(right))):
        if left[i] != right[i]:
            explanation += ['At index %s diff: %r != %r' %
                            (i, left[i], right[i])]
            break
    if len(left) > len(right):
        explanation += ['Left contains more items, '
            'first extra item: %s' % py.io.saferepr(left[len(right)],)]
    elif len(left) < len(right):
        explanation += ['Right contains more items, '
            'first extra item: %s' % py.io.saferepr(right[len(left)],)]
    return explanation # + _diff_text(py.std.pprint.pformat(left),
                       #             py.std.pprint.pformat(right))


def _compare_eq_set(left, right):
    explanation = []
    diff_left = left - right
    diff_right = right - left
    if diff_left:
        explanation.append('Extra items in the left set:')
        for item in diff_left:
            explanation.append(py.io.saferepr(item))
    if diff_right:
        explanation.append('Extra items in the right set:')
        for item in diff_right:
            explanation.append(py.io.saferepr(item))
    return explanation


def _notin_text(term, text):
    index = text.find(term)
    head = text[:index]
    tail = text[index+len(term):]
    correct_text = head + tail
    diff = _diff_text(correct_text, text)
    newdiff = ['%s is contained here:' % py.io.saferepr(term, maxsize=42)]
    for line in diff:
        if line.startswith('Skipping'):
            continue
        if line.startswith('- '):
            continue
        if line.startswith('+ '):
            newdiff.append('  ' + line[2:])
        else:
            newdiff.append(line)
    return newdiff
