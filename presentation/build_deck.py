from pathlib import Path
from html import escape
from zipfile import ZipFile, ZIP_DEFLATED
import json
OUT=Path(__file__).resolve().parent
slides=[
("DATASURGE / AI DATA CENTER OPERATIONS","Keep AI running.\nKeep people one step ahead.","From the first warning to the next shift.",[("SEE THE IMPACT","Know what depends on what."),("ACT WITH CONTEXT","Get the right person involved."),("HAND OFF CLEARLY","Carry open work forward.")],"0:00–0:15","Behind every AI model is a data center, and a team keeping it alive around the clock. Datasurge helps that team see what is at risk, act with context, and pass the work on clearly."),
("01 / THE PROBLEM","The warning exists.\nThe response breaks down.","Three gaps between knowing something and doing something.",[("MISSED WARNING","An important alert gets lost in the noise."),("UNCLEAR HANDOFF","The next shift inherits a problem without its history."),("WRONG INFORMATION","The right engineer gets too little context, too late.")],"0:15–0:40","The challenge is not just detecting failures. An important warning gets buried among routine alerts. A night-shift engineer leaves without passing on an unresolved issue. Or an incident reaches someone who cannot fix it. These are gaps between monitoring and coordinated action. We built Datasurge around those three gaps."),
("02 / SEE THE IMPACT","One cooling fault.\nA chain of consequences.","Click a component to trace downstream risk.",[("CHILLER","Cooling is lost"),("GPU RACKS","Temperature rises"),("AI WORKLOADS","Service is at risk")],"0:40–1:10","Here is our example: a cooling failure in us-east. The dependency map connects that chiller to the racks, GPUs, and workloads that depend on it. Selecting a component highlights downstream risk and shows affected workloads, customer exposure, and estimated time to impact. Operators can also preview maintenance in what-if mode. These are simulated forecasts, not measurements from real hardware."),
("03 / ACT WITH CONTEXT","Give the right person\na clear next step.","Prioritize the incident. Explain the options. Track the action.",[("TRIAGE","Group related alerts. Route incidents by specialization."),("ESCALATE","Track acknowledgment. Escalate when nobody responds."),("PROTECT WORKLOADS","Suggest compatible moves. Approve migration or checkpoint.")],"1:10–1:40","Related alerts are grouped into an incident and routed to an on-shift specialist. If nobody acknowledges it, the incident escalates. The workload planner evaluates capacity, hardware, latency, and risk before suggesting a move. An operator approves the action. If a workload cannot move safely, checkpointing may be the right option. The timeline records what happened and who acted."),
("04 / KEEP THE CONTEXT","A shift change should\nnot erase what you know.","The next engineer starts with the story, not a blank screen.",[("SHIFT HANDOFF","Open incidents and watch items.\nPending moves and commitments.\nAcknowledge each item."),("ASK DATASURGE","Ask Gemini about the simulation.\nGet plain-English explanations.\nOperators control actions.")],"1:40–2:10","At shift change, Datasurge carries forward open incidents, watch items, pending migrations, and commitments to other teams. The incoming engineer acknowledges each item. Gemini is a separate assistant for questions about the current simulation. Handoff reports still have an offline template path, so the core demo does not depend on an AI response. The assistant explains; operators control actions."),
("05 / LIVE DEMO","One incident.\nA complete operational story.","See the risk. Coordinate the response. Preserve the handoff.",[("1 / TRIGGER","Cooling failure in us-east"),("2 / TRACE","Select the chiller; show impact"),("3 / RESPOND","Show the owner and a suggested move"),("4 / HAND OFF","Open report; acknowledge an item")],"2:10–3:00","Switch to the prepared app. Say: I am triggering a cooling failure in us-east. This is the component that failed, and these are the workloads downstream. The incident has an owner and an acknowledgment countdown. Here is a workload recommendation and the reasoning behind it. Finally, the handoff keeps the next engineer informed and asks them to acknowledge the open work. Close with: Datasurge connects a warning to its impact, its owner, and its next action—so the team can stay one step ahead.")
]
NS='http://schemas.openxmlformats.org'
D=f'xmlns:a="{NS}/drawingml/2006/main" xmlns:r="{NS}/officeDocument/2006/relationships" xmlns:p="{NS}/presentationml/2006/main"'
G='<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
C='<p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/>'
def xml(s):return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+s
def rel(items):return xml(f'<Relationships xmlns="{NS}/package/2006/relationships">'+''.join(f'<Relationship Id="{i}" Type="{NS}/officeDocument/2006/relationships/{t}" Target="{p}"/>' for i,t,p in items)+'</Relationships>')
def e(n):return round(n*914400)
def box(i,x,y,w,h,text='',size=20,color='EFF3F8',fill=None,bold=False):
 paras=''.join(f'<a:p><a:r><a:rPr lang="en-US" sz="{size*100}" b="{int(bold)}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="Arial"/></a:rPr><a:t>{escape(line)}</a:t></a:r></a:p>' for line in text.split('\n'))
 paint=f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else '<a:noFill/>'
 return f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Element {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{e(x)}" y="{e(y)}"/><a:ext cx="{e(w)}" cy="{e(h)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>{paint}<a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="0" rIns="0" tIns="0" bIns="0"/><a:lstStyle/>{paras}</p:txBody></p:sp>'
types=[('/ppt/presentation.xml','presentationml.presentation.main'),('/ppt/slideMasters/slideMaster1.xml','presentationml.slideMaster'),('/ppt/slideLayouts/slideLayout1.xml','presentationml.slideLayout'),('/ppt/notesMasters/notesMaster1.xml','presentationml.notesMaster')]
for n in range(1,7):types.extend([(f'/ppt/slides/slide{n}.xml','presentationml.slide'),(f'/ppt/notesSlides/notesSlide{n}.xml','presentationml.notesSlide')])
with ZipFile(OUT/'datasurge-pitch.pptx','w',ZIP_DEFLATED) as z:
 def put(p,s):z.writestr(p,s)
 put('[Content_Types].xml',xml(f'<Types xmlns="{NS}/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'+''.join(f'<Override PartName="{p}" ContentType="application/vnd.openxmlformats-officedocument.{t}+xml"/>' for p,t in types)+'</Types>'))
 put('_rels/.rels',rel([('rId1','officeDocument','ppt/presentation.xml')]))
 put('ppt/presentation.xml',xml(f'<p:presentation {D}><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId7"/></p:sldMasterIdLst><p:notesMasterIdLst><p:notesMasterId r:id="rId8"/></p:notesMasterIdLst><p:sldIdLst>'+''.join(f'<p:sldId id="{255+n}" r:id="rId{n}"/>' for n in range(1,7))+f'</p:sldIdLst><p:sldSz cx="{e(13.333)}" cy="{e(7.5)}"/><p:notesSz cx="{e(7.5)}" cy="{e(10)}"/></p:presentation>'))
 put('ppt/_rels/presentation.xml.rels',rel([(f'rId{n}','slide',f'slides/slide{n}.xml') for n in range(1,7)]+[('rId7','slideMaster','slideMasters/slideMaster1.xml'),('rId8','notesMaster','notesMasters/notesMaster1.xml')]))
 put('ppt/slideMasters/slideMaster1.xml',xml(f'<p:sldMaster {D}><p:cSld><p:spTree>{G}</p:spTree></p:cSld>{C}<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>'))
 put('ppt/slideMasters/_rels/slideMaster1.xml.rels',rel([('rId1','slideLayout','../slideLayouts/slideLayout1.xml')]))
 put('ppt/slideLayouts/slideLayout1.xml',xml(f'<p:sldLayout {D} type="blank" preserve="1"><p:cSld name="Blank"><p:spTree>{G}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>'))
 put('ppt/slideLayouts/_rels/slideLayout1.xml.rels',rel([('rId1','slideMaster','../slideMasters/slideMaster1.xml')]))
 put('ppt/notesMasters/notesMaster1.xml',xml(f'<p:notesMaster {D}><p:cSld><p:spTree>{G}</p:spTree></p:cSld>{C}</p:notesMaster>'))
 for n,(k,t,sub,cards,timing,notes) in enumerate(slides,1):
  shapes=box(2,0,0,13.333,7.5,fill='090B0F')+box(3,.65,.48,12,.3,k,11,'69A6FF',bold=True)+box(4,.65,1.18,12,1.85,t,43 if n==1 else 40)+box(5,.68,3.25,12,.6,sub,20,'A7B3C5')
  w=(12-.3*(len(cards)-1))/len(cards)
  for j,(label,body) in enumerate(cards):
   x=.67+j*(w+.3)
   shapes+=box(10+j*4,x,4.25,w,1.85,fill='151A22')+box(11+j*4,x+.18,4.48,w-.36,.45,label,13,'69A6FF',bold=True)+box(12+j*4,x+.18,5.02,w-.36,1.05,body,16)
   if n==3 and j<2:shapes+=box(50+j,x+w+.04,4.9,.25,.4,'›',23,'69A6FF')
  shapes+=box(80,.67,6.9,11,.25,'DATASURGE / WORKING PROTOTYPE / SIMULATED INFRASTRUCTURE',9,'8995A7')+box(81,12,6.85,.65,.3,f'{n:02d} / 06',10,'8995A7')
  put(f'ppt/slides/slide{n}.xml',xml(f'<p:sld {D}><p:cSld><p:spTree>{G}{shapes}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'))
  put(f'ppt/slides/_rels/slide{n}.xml.rels',rel([('rId1','slideLayout','../slideLayouts/slideLayout1.xml'),('rId2','notesSlide',f'../notesSlides/notesSlide{n}.xml')]))
  body=box(2,.5,1,6,7,timing+'\n\n'+notes,14).replace('<p:nvPr/>','<p:nvPr><p:ph type="body" idx="1"/></p:nvPr>')
  put(f'ppt/notesSlides/notesSlide{n}.xml',xml(f'<p:notes {D}><p:cSld><p:spTree>{G}{body}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>'))
  put(f'ppt/notesSlides/_rels/notesSlide{n}.xml.rels',rel([('rId1','slide',f'../slides/slide{n}.xml'),('rId2','notesMaster','../notesMasters/notesMaster1.xml')]))
script='# Datasurge — three-minute pitch\n\nSix slides. Total: 180 seconds. Speaker notes are embedded in the PowerPoint.\n\n'
for n,s in enumerate(slides,1):script+=f'## {n}. {s[1].replace(chr(10)," ")} ({s[4]})\n\n{s[5]}\n\n'
script+='''## Before presenting

- Start the app and test Gemini ahead of time. Do not wait for an AI response on stage.
- Reset the simulation, select us-east, and rehearse the cooling-failure preset.
- Keep the app in a second tab. Prepare the shift handoff in advance if advancing the simulation takes too long.
- Show one migration recommendation. Do not wait for every workload to finish moving.
- Impact estimates and migration targets depend on simulation state. Describe only what the app shows.
- Gemini powers interactive Q&A. Reports retain the existing Claude/template path; no Claude key is currently configured.
- The graph uses dependency columns, not a radial mind map.
- This is a simulated prototype. Do not claim measured outage reduction, production deployment, or customer traction.

## 50-second demo cue sheet

| Time | Action | Say |
| --- | --- | --- |
| 0–10 s | Trigger cooling failure in us-east. | One fault starts the chain. |
| 10–20 s | Select the affected chiller. | Here are its downstream workloads and predicted risk. |
| 20–30 s | Open the incident. | A specialist owns it; silence triggers escalation. |
| 30–40 s | Show a workload suggestion; approve if ready. | We explain the move before asking for approval. |
| 40–50 s | Show the prepared handoff and acknowledge an item. | The next engineer receives the context, not just the alert. |

If no recommendation is ready, describe the planner without claiming a completed migration. If the live app fails, narrate slide 6.

## Opening the deck

Open datasurge-pitch.pptx in PowerPoint, Keynote, or Google Slides.
Or open datasurge-pitch.html in a browser: arrow keys navigate, F requests fullscreen, N toggles notes.
'''
(OUT/'speaker-script.md').write_text(script)
html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>datasurge — three-minute pitch</title><style>
*{box-sizing:border-box}body{margin:0;background:#090b0f;color:#eff3f8;font-family:Arial,Helvetica,sans-serif}main{max-width:1440px;margin:auto}section{min-height:calc(100vh - 60px);padding:5vh 5vw;display:none;flex-direction:column}section.active{display:flex}.eyebrow{font-size:13px;letter-spacing:.16em;color:#69a6ff;font-weight:700}h1{font-size:clamp(36px,5vw,74px);line-height:1.08;font-weight:400;letter-spacing:-.045em;white-space:pre-line;margin:6vh 0 20px}.sub{font-size:clamp(17px,2vw,27px);color:#a7b3c5;margin:0 0 5vh}.cards{display:grid;gap:24px;margin:auto 0 5vh;grid-template-columns:repeat(var(--count),1fr)}article{padding:26px;background:#151a22;border-top:2px solid #354354;position:relative}h2{color:#69a6ff;font-size:15px;letter-spacing:.04em;margin:0 0 22px}article p{font-size:clamp(16px,1.65vw,23px);line-height:1.5;white-space:pre-line;margin:0}.flow article:not(:last-child):after{content:"›";position:absolute;right:-20px;top:45%;font-size:30px;color:#69a6ff}footer{font-size:11px;letter-spacing:.12em;color:#8995a7;display:flex;justify-content:space-between}nav{height:60px;display:flex;align-items:center;justify-content:center;gap:20px;border-top:1px solid #252c36}button{background:none;color:#a7b3c5;border:1px solid #354354;padding:8px 14px;border-radius:4px;cursor:pointer}button:focus-visible{outline:2px solid #69a6ff}#notes{display:none;max-width:1000px;margin:20px auto;padding:24px;line-height:1.6;color:#b9c7da}#notes.visible{display:block}@media(max-width:650px){.cards{grid-template-columns:1fr;margin-top:20px}article{padding:16px}h2{margin-bottom:8px}h1{margin-top:30px}.flow article:after{display:none}}@media print{section,section.active{display:flex;min-height:7.5in;page-break-after:always}nav,#notes{display:none!important}@page{size:13.333in 7.5in;margin:0}}
</style><main>'''
for n,s in enumerate(slides,1):
 html+=f'<section class="{"active" if n==1 else ""} {"flow" if n==3 else ""}" aria-label="Slide {n}"><div class="eyebrow">{escape(s[0])}</div><h1>{escape(s[1])}</h1><p class="sub">{escape(s[2])}</p><div class="cards" style="--count:{len(s[3])}">'
 for title,body in s[3]:html+=f'<article><h2>{escape(title)}</h2><p>{escape(body)}</p></article>'
 html+=f'</div><footer><span>DATASURGE / SIMULATED INFRASTRUCTURE</span><span>{n:02d} / 06</span></footer></section>'
html+='''</main><nav><button id="prev" aria-label="Previous slide">←</button><span id="count"></span><button id="next" aria-label="Next slide">→</button><button id="full">Fullscreen</button><button id="toggle">Speaker notes</button></nav><aside id="notes"></aside><script>const data='''+json.dumps(slides)+''';let current=0;const slides=[...document.querySelectorAll("section")];function show(n){current=Math.max(0,Math.min(slides.length-1,n));slides.forEach((s,i)=>s.classList.toggle("active",i===current));document.querySelector("#count").textContent=(current+1)+" / "+slides.length;document.querySelector("#notes").textContent=data[current][4]+" — "+data[current][5];}function full(){if(!document.fullscreenElement)document.documentElement.requestFullscreen?.().catch(()=>{});else document.exitFullscreen?.();}document.querySelector("#prev").onclick=()=>show(current-1);document.querySelector("#next").onclick=()=>show(current+1);document.querySelector("#full").onclick=full;document.querySelector("#toggle").onclick=()=>document.querySelector("#notes").classList.toggle("visible");document.addEventListener("keydown",e=>{if(e.target.tagName==="BUTTON"&&e.key===" ")return;if(["ArrowRight","PageDown"," "].includes(e.key)){e.preventDefault();show(current+1)}if(["ArrowLeft","PageUp"].includes(e.key))show(current-1);if(e.key.toLowerCase()==="f")full();if(e.key.toLowerCase()==="n")document.querySelector("#toggle").click();});show(0);</script></html>'''
(OUT/'datasurge-pitch.html').write_text(html)
print('Created PPTX, browser deck, and timed speaker script.')
