from app.supervisor import Supervisor


class Process:
    def __init__(self):
        self.code = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.code

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


def source(id, **overrides):
    return dict(id=id, sourceType='rtsp', enabled=True, status='online', **overrides)


def test_supervisor_caps_workers_and_waits_for_shutdown_before_replacement():
    started = []
    def launch(id):
        process = Process()
        started.append((id, process))
        return process
    manager = Supervisor(launch, capacity=2)
    manager.reconcile([source('a'), source('b'), source('c')], now=0)
    assert [id for id, _ in started] == ['a', 'b']
    manager.reconcile([source('b'), source('c')], now=1)
    assert started[0][1].terminated
    assert len(started) == 2
    started[0][1].code = 0
    manager.reconcile([source('b'), source('c')], now=2)
    assert [id for id, _ in started] == ['a', 'b', 'c']


def test_crashes_back_off_and_stuck_shutdown_is_killed():
    processes = []
    def launch(id):
        process = Process()
        processes.append(process)
        return process
    manager = Supervisor(launch, capacity=1)
    manager.reconcile([source('a')], now=0)
    processes[0].code = 1
    manager.reconcile([source('a')], now=1)
    manager.reconcile([source('a')], now=5)
    assert len(processes) == 1
    manager.reconcile([source('a')], now=6)
    assert len(processes) == 2
    manager.reconcile([], now=7)
    assert processes[-1].terminated
    manager.reconcile([], now=38)
    assert processes[-1].killed


def test_disabled_paused_and_file_sources_do_not_start():
    started = []
    manager = Supervisor(lambda id: started.append(id), capacity=3)
    rows = [source('a'), source('b'), source('c')]
    rows[0]['enabled'] = False
    rows[1]['status'] = 'paused'
    rows[2]['sourceType'] = 'file'
    manager.reconcile(rows, now=0)
    assert started == []
