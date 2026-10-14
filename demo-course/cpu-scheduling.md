# Remaining time

CPU scheduling chooses which ready process receives the CPU. Arrival time is when a process becomes ready. Burst time is the total CPU execution it requires. Executed time counts only time actually spent running, not time spent waiting.

Remaining time = original burst time - executed CPU time. Waiting does not reduce remaining time. Recompute remaining work at each scheduling event. Distinguishing original burst from remaining time is a prerequisite for applying shortest remaining time first.

# Shortest remaining time first

SRTF is the preemptive form of shortest job first. At an arrival or completion, compare the remaining CPU time of every ready process, including the running process. A newly arrived process has not executed yet, so its remaining time equals its burst time.

If the newcomer needs less time than the current process still needs, preempt. If the current process has less remaining work, it continues. Comparing a newcomer with the running process's original burst ignores work already completed and can reverse the correct decision.

For equal remaining times, this course uses arrival time and then original input order. One CPU executes one process at a time. If nothing is ready, it is idle. This model uses integer ticks and no context-switch cost.

# Scheduling metrics

Completion time is the instant a process finishes. Turnaround time = completion time - arrival time. Waiting time = turnaround time - burst time. Response time = first execution time - arrival time. Average a metric across all processes, including processes with zero waiting time.

Draw the execution timeline first. Account for every burst exactly once across its execution segments. A process cannot run before arriving. Preemption can split a process's execution into multiple segments without changing its total required burst.
