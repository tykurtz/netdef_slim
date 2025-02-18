import tensorflow as tf
import os, sys, time
import netdef_slim as nd
from netdef_slim.tensorflow.tools.trainer.simpletrainer import SimpleTrainer
import numpy as np
import time
from netdef_slim.utils.io import read
import timeit

class NetActions:

    def __init__(self, net_dir, save_snapshots=True, save_summaries=True):
        self._check_evo_manager_init()
        self.net = nd.load_module(os.path.join(net_dir, 'net.py'))
        self.net_dir = net_dir

        height = 480
        width = 640

        tf.reset_default_graph()
        last_evo, current_evo = nd.evo_manager.get_status()
        self.env = self.net.get_env()
        print('Evolution: ' + last_evo.path())

        self.eval_out = self.env.make_eval_graph(
            width = width,
            height = height,
        )

        self.session = self._create_session()
        self.trainer = SimpleTrainer(session=self.session, train_dir=last_evo.path())
        self.session.run(tf.global_variables_initializer())

        ignore_vars = []
        if len(tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope="copy")) > 0:
            ignore_vars = [tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope="copy")[0]]
        state = last_evo.last_state()
        self.trainer.load_checkpoint(state.path(), ignore_vars=ignore_vars)

        placeholders = tf.get_collection('placeholders')
        self.img0 = placeholders[0]
        self.img1 = placeholders[1]

    def _check_evo_manager_init(self):
        if (len(nd.evo_manager.evolutions()) == 0):
            raise ValueError('Evolutions are empty. Make sure evo manager has correctly loaded config.py in your network directory')

    def _create_session(self):
        config = tf.ConfigProto(log_device_placement=False)
        config.gpu_options.allow_growth = True
        session = tf.Session(config = config)
        return session


    def load_params(self, trainer, last_evo, finetune=False, weights=None):
        ignore_vars = None
        last_state = last_evo.last_state()
        if last_evo.is_complete() or finetune:
            ignore_vars = self.get_ignore_vars(defaults =[trainer.global_step()])

        if weights is not None:
            trainer.load_checkpoint(weights, ignore_vars=ignore_vars)
        elif last_state is not None:
            trainer.load_checkpoint(last_state.path(), ignore_vars=ignore_vars)

    def eval(self, image_0, image_1, state=None):
        nd.phase = 'test'
        if isinstance(image_0, str): image_0=read(image_0).transpose(2, 0, 1)[np.newaxis, :, :, :].astype(np.float32)
        if isinstance(image_1, str): image_1=read(image_1).transpose(2, 0, 1)[np.newaxis, :, :, :].astype(np.float32)
        height = image_0.shape[2]
        width = image_0.shape[3]
        print(f'Height: {height} Width: {width}')


        out = self.session.run(self.eval_out.get_list(), feed_dict={ self.img0: image_0,
                                                                self.img1: image_1})
        return out


    def perf_test(self, iters, burn_in, resolution):
        nd.phase = 'test'
        width, height = resolution
        env = self.net.get_env()
        eval_out = env.make_perf_test_graph(
                                        width = int(width),
                                        height = int(height),
                                        )
        session = self._create_session()
        session.run(tf.global_variables_initializer())
        times = []
        for i in range(0, burn_in + iters):
            if i<burn_in:
                if i==0: print('Burn-in phase')
                session.run(eval_out.get_list())
            else:
                start = timeit.default_timer()
                out = session.run(eval_out.get_list())
                stop = timeit.default_timer()
                secs = stop - start
                times.append(secs)
                avg_time=np.mean(times)
        print("============== Perf test results ============")
        print("Input resolution: {}".format(resolution))
        print('Burn-in iters: {}'.format(burn_in))
        print('Run iters: {}'.format(iters))
        print("Average fwd pass time: {} s".format(avg_time))
