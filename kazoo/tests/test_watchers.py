import time
import threading
import uuid

from nose.tools import eq_
from nose.tools import raises

from kazoo.protocol.states import KazooState
from kazoo.testing import KazooTestCase


class KazooDataWatcherTests(KazooTestCase):
    def setUp(self):
        super(KazooDataWatcherTests, self).setUp()
        self.path = "/" + uuid.uuid4().hex
        self.client.ensure_path(self.path)

    def test_data_watcher(self):
        update = threading.Event()
        data = [True]

        @self.client.DataWatch(self.path)
        def changed(d, stat):
            data.pop()
            data.append(d)
            update.set()

        update.wait(10)
        eq_(data, [b""])
        update.clear()

        self.client.set(self.path, b'fred')
        update.wait(10)
        eq_(data[0], b'fred')
        update.clear()

    def test_data_watcher2(self):
        update = threading.Event()
        data = [True]

        # Make it a non-existent path
        self.path += 'f'

        @self.client.DataWatch(self.path, allow_missing_node=True)
        def changed(d, stat):
            data.pop()
            data.append(d)
            update.set()

        update.wait(10)
        eq_(data, [None])
        update.clear()

        self.client.create(self.path, b'fred')
        update.wait(10)
        eq_(data[0], b'fred')
        update.clear()

    def test_func_style_data_watch(self):
        update = threading.Event()
        data = [True]

        def changed(d, stat):
            data.pop()
            data.append(d)
            update.set()
        self.client.DataWatch(self.path, changed)

        update.wait(10)
        eq_(data, [b""])
        update.clear()

        self.client.set(self.path, b'fred')
        update.wait(10)
        eq_(data[0], b'fred')
        update.clear()

    def test_func_style_data_watch2(self):
        update = threading.Event()
        data = [True]

        # Make it a non-existent path
        self.path += 'f'

        def changed(d, stat):
            data.pop()
            data.append(d)
            update.set()
        self.client.DataWatch(self.path, changed, allow_missing_node=True)

        update.wait(10)
        eq_(data, [None])
        update.clear()

        self.client.create(self.path, b'fred')
        update.wait(10)
        eq_(data[0], b'fred')
        update.clear()

    def test_datawatch_across_session_expire(self):
        update = threading.Event()
        data = [True]

        @self.client.DataWatch(self.path)
        def changed(d, stat):
            data.pop()
            data.append(d)
            update.set()

        update.wait(10)
        eq_(data, [b""])
        update.clear()

        self.expire_session()
        self.client.retry(self.client.set, self.path, b'fred')
        update.wait(25)
        eq_(data[0], b'fred')

    def test_datawatch_across_session_expire2(self):
        update = threading.Event()
        data = [True]

        self.path += "f"

        @self.client.DataWatch(self.path, allow_missing_node=True)
        def changed(d, stat):
            data.pop()
            data.append(d)
            update.set()

        update.wait(10)
        eq_(data, [None])
        update.clear()

        self.expire_session()
        eq_(data, [None])
        update.wait(10)
        update.clear()
        self.client.retry(self.client.create, self.path, b'fred')
        update.wait(25)
        eq_(data[0], b'fred')

    def test_func_stops(self):
        update = threading.Event()
        data = [True]

        fail_through = []

        @self.client.DataWatch(self.path)
        def changed(d, stat):
            data.pop()
            data.append(d)
            update.set()
            if fail_through:
                return False

        update.wait(10)
        eq_(data, [b""])
        update.clear()

        fail_through.append(True)
        self.client.set(self.path, b'fred')
        update.wait(10)
        eq_(data[0], b'fred')
        update.clear()

        self.client.set(self.path, b'asdfasdf')
        update.wait(0.2)
        eq_(data[0], b'fred')

        d, stat = self.client.get(self.path)
        eq_(d, b'asdfasdf')

    def test_func_stops2(self):
        update = threading.Event()
        data = [True]

        self.path += "f"

        fail_through = []

        @self.client.DataWatch(self.path, allow_missing_node=True)
        def changed(d, stat):
            data.pop()
            data.append(d)
            update.set()
            if fail_through:
                return False

        update.wait(10)
        eq_(data, [None])
        update.clear()

        fail_through.append(True)
        self.client.create(self.path, b'fred')
        update.wait(10)
        eq_(data[0], b'fred')
        update.clear()

        self.client.set(self.path, b'asdfasdf')
        update.wait(0.2)
        eq_(data[0], b'fred')

        d, stat = self.client.get(self.path)
        eq_(d, b'asdfasdf')

    def test_no_such_node(self):
        args = []

        @self.client.DataWatch("/some/path")
        def changed(d, stat):
            args.extend([d, stat])

        eq_(args, [None, None])

    def test_no_such_node2(self):
        args = []

        @self.client.DataWatch("/some/path", allow_missing_node=True)
        def changed(d, stat):
            args.extend([d, stat])

        eq_(args, [None, None])

    def test_bad_watch_func(self):
        counter = 0

        @self.client.DataWatch(self.path)
        def changed(d, stat):
            if counter > 0:
                raise Exception("oops")

        raises(Exception)(changed)

        counter += 1
        self.client.set(self.path, b'asdfasdf')

    def test_bad_watch_func2(self):
        counter = 0

        @self.client.DataWatch(self.path, allow_missing_node=True)
        def changed(d, stat):
            if counter > 0:
                raise Exception("oops")

        raises(Exception)(changed)

        counter += 1
        self.client.set(self.path, b'asdfasdf')

    def test_watcher_evaluating_to_false(self):
        class WeirdWatcher(list):
            def __call__(self, *args):
                self.called = True
        watcher = WeirdWatcher()
        self.client.DataWatch(self.path, watcher)
        self.client.set(self.path, b'mwahaha')
        self.assertTrue(watcher.called)

    def test_watcher_repeat_delete(self):
        a = []
        ev = threading.Event()

        self.client.delete(self.path)

        @self.client.DataWatch(self.path, allow_missing_node=True)
        def changed(val, stat):
            a.append(val)
            ev.set()
        eq_(a, [None])
        ev.wait(10)
        ev.clear()
        self.client.create(self.path, b'blah')
        ev.wait(10)
        ev.clear()
        eq_(a, [None, b'blah'])
        self.client.delete(self.path)
        ev.wait(10)
        ev.clear()
        eq_(a, [None, b'blah', None])
        self.client.create(self.path, b'blah')
        ev.wait(10)
        ev.clear()
        eq_(a, [None, b'blah', None, b'blah'])

    def test_watcher_with_closing(self):
        a = []
        ev = threading.Event()

        self.client.delete(self.path)

        @self.client.DataWatch(self.path, allow_missing_node=True)
        def changed(val, stat):
            a.append(val)
            ev.set()
        eq_(a, [None])

        b = False
        try:
            self.client.stop()
        except:
            b = True
        eq_(b, False)


class KazooChildrenWatcherTests(KazooTestCase):
    def setUp(self):
        super(KazooChildrenWatcherTests, self).setUp()
        self.path = "/" + uuid.uuid4().hex
        self.client.ensure_path(self.path)

    def test_child_watcher(self):
        update = threading.Event()
        all_children = ['fred']

        @self.client.ChildrenWatch(self.path)
        def changed(children):
            while all_children:
                all_children.pop()
            all_children.extend(children)
            update.set()

        update.wait(10)
        eq_(all_children, [])
        update.clear()

        self.client.create(self.path + '/' + 'smith')
        update.wait(10)
        eq_(all_children, ['smith'])
        update.clear()

        self.client.create(self.path + '/' + 'george')
        update.wait(10)
        eq_(sorted(all_children), ['george', 'smith'])

    def test_func_style_child_watcher(self):
        update = threading.Event()
        all_children = ['fred']

        def changed(children):
            while all_children:
                all_children.pop()
            all_children.extend(children)
            update.set()

        self.client.ChildrenWatch(self.path, changed)

        update.wait(10)
        eq_(all_children, [])
        update.clear()

        self.client.create(self.path + '/' + 'smith')
        update.wait(10)
        eq_(all_children, ['smith'])
        update.clear()

        self.client.create(self.path + '/' + 'george')
        update.wait(10)
        eq_(sorted(all_children), ['george', 'smith'])

    def test_func_stops(self):
        update = threading.Event()
        all_children = ['fred']

        fail_through = []

        @self.client.ChildrenWatch(self.path)
        def changed(children):
            while all_children:
                all_children.pop()
            all_children.extend(children)
            update.set()
            if fail_through:
                return False

        update.wait(10)
        eq_(all_children, [])
        update.clear()

        fail_through.append(True)
        self.client.create(self.path + '/' + 'smith')
        update.wait(10)
        eq_(all_children, ['smith'])
        update.clear()

        self.client.create(self.path + '/' + 'george')
        update.wait(0.5)
        eq_(all_children, ['smith'])

    def test_child_watch_session_loss(self):
        update = threading.Event()
        all_children = ['fred']

        @self.client.ChildrenWatch(self.path)
        def changed(children):
            while all_children:
                all_children.pop()
            all_children.extend(children)
            update.set()

        update.wait(10)
        eq_(all_children, [])
        update.clear()

        self.client.create(self.path + '/' + 'smith')
        update.wait(10)
        eq_(all_children, ['smith'])
        update.clear()
        self.expire_session()

        self.client.retry(self.client.create,
                          self.path + '/' + 'george')
        update.wait(20)
        eq_(sorted(all_children), ['george', 'smith'])

    def test_child_stop_on_session_loss(self):
        update = threading.Event()
        all_children = ['fred']

        @self.client.ChildrenWatch(self.path, allow_session_lost=False)
        def changed(children):
            while all_children:
                all_children.pop()
            all_children.extend(children)
            update.set()

        update.wait(10)
        eq_(all_children, [])
        update.clear()

        self.client.create(self.path + '/' + 'smith')
        update.wait(10)
        eq_(all_children, ['smith'])
        update.clear()
        self.expire_session()

        self.client.retry(self.client.create,
                          self.path + '/' + 'george')
        update.wait(4)
        eq_(update.is_set(), False)
        eq_(all_children, ['smith'])

        children = self.client.get_children(self.path)
        eq_(sorted(children), ['george', 'smith'])

    def test_bad_children_watch_func(self):
        counter = 0

        @self.client.ChildrenWatch(self.path)
        def changed(children):
            if counter > 0:
                raise Exception("oops")

        raises(Exception)(changed)
        counter += 1
        self.client.create(self.path + '/' + 'smith')


class KazooPatientChildrenWatcherTests(KazooTestCase):
    def setUp(self):
        super(KazooPatientChildrenWatcherTests, self).setUp()
        self.path = "/" + uuid.uuid4().hex

    def _makeOne(self, *args, **kwargs):
        from kazoo.recipe.watchers import PatientChildrenWatch
        return PatientChildrenWatch(*args, **kwargs)

    def test_watch(self):
        self.client.ensure_path(self.path)
        watcher = self._makeOne(self.client, self.path, 0.1)
        result = watcher.start()
        children, asy = result.get()
        eq_(len(children), 0)
        eq_(asy.ready(), False)

        self.client.create(self.path + '/' + 'fred')
        asy.get(timeout=1)
        eq_(asy.ready(), True)

    def test_exception(self):
        from kazoo.exceptions import NoNodeError
        watcher = self._makeOne(self.client, self.path, 0.1)
        result = watcher.start()

        @raises(NoNodeError)
        def testit():
            result.get()
        testit()

    def test_watch_iterations(self):
        self.client.ensure_path(self.path)
        watcher = self._makeOne(self.client, self.path, 0.5)
        result = watcher.start()
        eq_(result.ready(), False)

        time.sleep(0.08)
        self.client.create(self.path + '/' + uuid.uuid4().hex)
        eq_(result.ready(), False)
        time.sleep(0.08)
        eq_(result.ready(), False)
        self.client.create(self.path + '/' + uuid.uuid4().hex)
        time.sleep(0.08)
        eq_(result.ready(), False)

        children, asy = result.get()
        eq_(len(children), 2)


class KazooDataWatcherRestartTests(KazooTestCase):
    def setUp(self):
        self.setup_zookeeper(randomize_hosts=False)
        self.path = "/" + uuid.uuid4().hex
        self.client.ensure_path(self.path)

    def test_data_watcher(self):
        update = threading.Event()
        ev = threading.Event()
        events = []

        # Make it a non-existent path
        self.path += 'f'

        @self.client.DataWatch(self.path, allow_missing_node=True)
        def changed(data, stat):
            if data is not None:
                events.append(stat)
                update.set()

        @self.client.add_listener
        def listen(state):
            if state != KazooState.LOST:
                ev.set()

        self.client.create(self.path, b'fred')
        update.wait(10)
        update.clear()
        eq_(len(events), 1)

        self.cluster[0].stop()
        ev.wait(30)

        time.sleep(3)

        self.cluster[0].run()
        ev.wait(30)

        self.client.set(self.path, b'said')
        update.wait(10)
        update.clear()

        time.sleep(1)
        eq_(len(events), 2)
