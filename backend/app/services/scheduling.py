"""Event-driven deterministic single-CPU scheduling, without context-switch costs.

Ties: criterion, arrival, original input order. Smaller priority runs first.
RR arrivals at a quantum boundary join the queue before the preempted process.
Adjacent identical execution segments merge; dispatch decisions remain separate.
"""
from collections import deque
from app.schemas.scheduling import SchedulingInput


def solve(request: SchedulingInput) -> dict:
    processes = request.processes
    remaining = [p.burst for p in processes]
    starts, completion, segments, decisions = {}, {}, [], []
    pending = sorted(range(len(processes)), key=lambda i: (processes[i].arrival, i))
    ready = deque()
    time = 0

    def record(pid, start, end):
        if segments and segments[-1]['pid'] == pid and segments[-1]['end'] == start:
            segments[-1]['end'] = end
        else:
            segments.append(dict(pid=pid, start=start, end=end))

    def arrive():
        while pending and processes[pending[0]].arrival <= time:
            ready.append(pending.pop(0))

    while len(completion) < len(processes):
        arrive()
        if not ready:
            future = processes[pending[0]].arrival
            record(None, time, future)
            time = future
            arrive()
        algorithm = request.algorithm
        if algorithm == 'round_robin':
            index = ready.popleft()
        else:
            def rank(i):
                p = processes[i]
                criterion = remaining[i] if algorithm == 'srtf' else p.burst if algorithm == 'sjf' else p.priority if algorithm.startswith('priority') else p.arrival
                return criterion, p.arrival, i
            index = min(ready, key=rank)
            ready.remove(index)
        p = processes[index]
        starts.setdefault(index, time)
        duration = min(remaining[index], request.quantum) if algorithm == 'round_robin' else remaining[index]
        if algorithm in {'srtf', 'priority_preemptive'} and pending:
            duration = min(duration, processes[pending[0]].arrival-time)
        decisions.append(dict(time=time, pid=p.pid, remaining_before=remaining[index],
                              ready=[processes[i].pid for i in ready], algorithm=algorithm))
        record(p.pid, time, time+duration)
        time += duration
        remaining[index] -= duration
        arrive()
        if remaining[index]:
            ready.append(index)
        else:
            completion[index] = time
    metrics = []
    for i,p in enumerate(processes):
        turnaround = completion[i]-p.arrival
        metrics.append(dict(pid=p.pid, start=starts[i], completion=completion[i],
            turnaround=turnaround, waiting=turnaround-p.burst, response=starts[i]-p.arrival))
    return dict(algorithm=request.algorithm, units='ticks', segments=segments, processes=metrics,
        averages={k:sum(p[k] for p in metrics)/len(metrics) for k in ['completion','turnaround','waiting','response']},
        decisions=decisions, tie_breaking='criterion, arrival, original input order; lower priority first; RR boundary arrivals before requeue',
        assumptions=['One CPU', 'Integer ticks', 'No context-switch overhead'])


def answer_for(request: SchedulingInput, metric: str, pid: str | None) -> tuple[str, dict]:
    """A server-owned grading target; floating averages are represented as exact fractions."""
    from fractions import Fraction
    result = solve(request)
    allowed = {'completion','turnaround','waiting','response'}
    if metric not in allowed:
        raise ValueError('Unsupported scheduling metric')
    if pid is None:
        value = Fraction(sum(p[metric] for p in result['processes']),len(result['processes']))
    else:
        found = next((p for p in result['processes'] if p['pid']==pid),None)
        if found is None: raise ValueError('Unknown scheduling target process')
        value = Fraction(found[metric])
    return str(value), result
