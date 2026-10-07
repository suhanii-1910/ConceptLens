import pytest
from pydantic import ValidationError
from app.schemas.scheduling import SchedulingInput
from app.services.scheduling import solve,answer_for

ALGORITHMS=['fcfs','sjf','srtf','priority','priority_preemptive','round_robin']
def request(algorithm,rows,quantum=None):
    return SchedulingInput(algorithm=algorithm,processes=[dict(pid=p,arrival=a,burst=b,priority=pr) for p,a,b,pr in rows],quantum=quantum)

@pytest.mark.parametrize('algorithm',ALGORITHMS)
def test_single_idle(algorithm):
    r=request(algorithm,[('P',3,5,1)],2 if algorithm=='round_robin' else None)
    value=solve(r)
    assert value['segments']==[dict(pid=None,start=0,end=3),dict(pid='P',start=3,end=8)]
    assert value['processes']==[dict(pid='P',start=3,completion=8,turnaround=5,waiting=0,response=0)]
    assert value==solve(r)

@pytest.mark.parametrize('algorithm,expected',[
 ('fcfs',[('P1',0,8),('P2',8,12)]),('sjf',[('P1',0,8),('P2',8,12)]),
 ('srtf',[('P1',0,8),('P2',8,12)]),('priority',[('P1',0,8),('P2',8,12)]),
 ('priority_preemptive',[('P1',0,5),('P2',5,9),('P1',9,12)])])
def test_staggered_classic(algorithm,expected):
    out=solve(request(algorithm,[('P1',0,8,2),('P2',5,4,1)]))
    assert [(s['pid'],s['start'],s['end']) for s in out['segments']]==expected
    if algorithm=='srtf':
        assert out['processes'][1]==dict(pid='P2',start=8,completion=12,turnaround=7,waiting=3,response=3)
        assert out['averages']['waiting']==1.5

def test_srtf_reverse_and_multiple_preemption():
    out=solve(request('srtf',[('P1',0,9,None),('P2',4,3,None)]))
    assert out['segments']==[dict(pid='P1',start=0,end=4),dict(pid='P2',start=4,end=7),dict(pid='P1',start=7,end=12)]
    out=solve(request('srtf',[('A',0,8,None),('B',1,4,None),('C',2,1,None)]))
    assert [s['pid'] for s in out['segments']]==['A','B','C','B','A']
    assert [p['completion'] for p in out['processes']]==[13,6,3]
    assert [p['waiting'] for p in out['processes']]==[5,1,0]

@pytest.mark.parametrize('algorithm',ALGORITHMS)
def test_tie_and_idle_gap(algorithm):
    out=solve(request(algorithm,[('Z',1,2,1),('A',1,2,1),('B',9,1,1)],10 if algorithm=='round_robin' else None))
    assert [s['pid'] for s in out['segments']]==[None,'Z','A',None,'B']
    assert out['segments'][-2]==dict(pid=None,start=5,end=9)

def test_rr_boundary_wraparound():
    r=request('round_robin',[('A',0,5,None),('B',2,3,None),('C',2,1,None)],2)
    out=solve(r)
    assert [(s['pid'],s['start'],s['end']) for s in out['segments']]==[('A',0,2),('B',2,4),('C',4,5),('A',5,7),('B',7,8),('A',8,9)]
    assert [p['waiting'] for p in out['processes']]==[4,3,2]
    assert [p['response'] for p in out['processes']]==[0,0,2]
    assert answer_for(r,'waiting',None)[0]=='3'

@pytest.mark.parametrize('change',[{'algorithm':'bad'},{'processes':[]},{'quantum':0},{'quantum':2},
 {'processes':[dict(pid='P',arrival=-1,burst=2)]},{'processes':[dict(pid='P',arrival=0,burst=0)]},
 {'processes':[dict(pid='P',arrival=True,burst=2)]},{'algorithm':'priority'},
 {'algorithm':'round_robin'},{'processes':[dict(pid='P',arrival=0,burst=2),dict(pid='P',arrival=1,burst=3)]}])
def test_invalid(change):
    data=dict(algorithm='fcfs',processes=[dict(pid='P',arrival=0,burst=2)])
    with pytest.raises(ValidationError): SchedulingInput.model_validate({**data,**change})

@pytest.mark.parametrize('algorithm,order', [('fcfs',['A','B','C']),('sjf',['B','C','A']),('srtf',['B','C','A']),('priority',['C','B','A']),('priority_preemptive',['C','B','A']),('round_robin',['A','B','C','A','C','A'])])
def test_all_arrive_at_zero(algorithm,order):
    result=solve(request(algorithm,[('A',0,5,3),('B',0,2,2),('C',0,3,1)],2 if algorithm=='round_robin' else None))
    assert [s['pid'] for s in result['segments']]==order
    assert sum(p['turnaround']-p['waiting'] for p in result['processes'])==10
