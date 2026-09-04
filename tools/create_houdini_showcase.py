import urllib.request, json

LLM_URL = 'http://127.0.0.1:58421/v1/chat/completions'
HOUDINI_URL = 'http://127.0.0.1:8100/api'

def query_llm(prompt):
    payload = {
        'messages': [
            {'role': 'system', 'content': 'You are a Houdini VEX code generator. Output ONLY raw VEX code inside a ```c or ```vex codeblock. Do not include introductory text, explanations, or commentary.'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.1,
        'max_tokens': 1024
    }
    req = urllib.request.Request(LLM_URL, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
    content = res['choices'][0]['message']['content']
    if '```' in content:
        code = content.split('```')[1]
        if code.startswith('c\n') or code.startswith('vex\n') or code.startswith('cpp\n'):
            code = code.split('\n', 1)[1]
    else:
        code = content
    return code.strip()

def exec_houdini_python(code_str):
    payload = {
        'jsonrpc': '2.0',
        'method': 'execute_python',
        'params': {'code': code_str},
        'id': 1
    }
    req = urllib.request.Request(HOUDINI_URL, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

print('1. Querying Scherk minimal surface...')
code_scherk = query_llm('Procedural Scherk minimal surface on a grid with complex logarithmic height and color ramp')
print('2. Querying Bishop curve...')
code_bishop = query_llm('Generate a 3D procedural knot curve with Bishop parallel transport frames, tangent T, curvature kappa, and Cd ramp in a detail wrangle')
print('3. Querying PBD distance solver...')
code_pbd = query_llm('PBD position based dynamics distance constraint solver with ground plane collision and stiffness damping')
print('4. Querying RK4 streamline vortex...')
code_rk4 = query_llm('4th-order Runge-Kutta RK4 streamline advection with curlnoise velocity field and speed coloring')

print('Building Houdini showcase scene...')
h_code = """
import hou

with hou.undos.group("Build V10 Showcase Gallery"):
    for node_name in ['v10_minimal_surface', 'v10_bishop_knot', 'v10_pbd_cloth', 'v10_rk4_vortex']:
        n = hou.node('/obj/' + node_name)
        if n:
            n.destroy()
            
    # 1. Scherk Minimal Surface
    geo1 = hou.node('/obj').createNode('geo', 'v10_minimal_surface')
    grid1 = geo1.createNode('grid', 'surface_grid')
    grid1.parm('rows').set(120)
    grid1.parm('cols').set(120)
    grid1.parm('sizex').set(8.0)
    grid1.parm('sizey').set(8.0)
    w1 = geo1.createNode('attribwrangle', 'v10_scherk_solver')
    w1.setInput(0, grid1)
    w1.parm('snippet').set('''__CODE_SCHERK__''')
    w1.cook(force=True)
    geo1.layoutChildren()
    
    # 2. Bishop Curve & Flow
    geo2 = hou.node('/obj').createNode('geo', 'v10_bishop_knot')
    w2 = geo2.createNode('attribwrangle', 'v10_bishop_solver')
    w2.parm('class').set('detail')
    w2.parm('snippet').set('''__CODE_BISHOP__''')
    w2.cook(force=True)
    geo2.layoutChildren()
    
    # 3. PBD Distance Solver
    geo3 = hou.node('/obj').createNode('geo', 'v10_pbd_cloth')
    grid3 = geo3.createNode('grid', 'cloth_grid')
    grid3.parm('rows').set(30)
    grid3.parm('cols').set(30)
    grid3.parm('sizex').set(5.0)
    grid3.parm('sizey').set(5.0)
    w3 = geo3.createNode('attribwrangle', 'v10_pbd_solver')
    w3.setInput(0, grid3)
    w3.parm('snippet').set('''__CODE_PBD__''')
    w3.cook(force=True)
    geo3.layoutChildren()
    
    # 4. RK4 Streamline Vortex
    geo4 = hou.node('/obj').createNode('geo', 'v10_rk4_vortex')
    torus4 = geo4.createNode('torus', 'emitter_torus')
    torus4.parm('rows').set(40)
    torus4.parm('cols').set(40)
    w4 = geo4.createNode('attribwrangle', 'v10_rk4_solver')
    w4.setInput(0, torus4)
    w4.parm('snippet').set('''__CODE_RK4__''')
    w4.cook(force=True)
    geo4.layoutChildren()
    
    # Position object nodes
    geo1.setPosition(hou.Vector2(0, 0))
    geo2.setPosition(hou.Vector2(3, 0))
    geo3.setPosition(hou.Vector2(6, 0))
    geo4.setPosition(hou.Vector2(9, 0))
    
    geo1.setDisplayFlag(True)
    geo1.setRenderFlag(True)
    
print('HOUDINI_NODES_CREATED_SUCCESSFULLY')
""".replace('__CODE_SCHERK__', code_scherk).replace('__CODE_BISHOP__', code_bishop).replace('__CODE_PBD__', code_pbd).replace('__CODE_RK4__', code_rk4)

res = exec_houdini_python(h_code)
print('Houdini execution result:', res)
