# This is the script testing worker-worker tensor transport
# which is modified based on TensorFlow GitHub issue 6116
# 19-Jun-2017

import os
import portpicker
import subprocess
import sys
import tensorflow as tf
import threading
import time

flags = tf.flags
flags.DEFINE_integer("iters", 10, "No. of iterations")
flags.DEFINE_integer("data_mb", 128, "size of 1D tensor in MBs")
flags.DEFINE_string("task_index", "", "# of current task")
flags.DEFINE_string("port0", "12222", "port of worker1, used as master")
flags.DEFINE_string("port1", "12223", "port of worker2")
flags.DEFINE_boolean("verbose", False, "whether to have verbose logging")
flags.DEFINE_boolean("profile", False, "whether to collect CPU profile")
flags.DEFINE_boolean("use_gpu", False, "Whether to use GPU transfer")
FLAGS = flags.FLAGS

def session_config():
  optimizer_options = tf.OptimizerOptions(opt_level=tf.OptimizerOptions.L0)
  graph_options = tf.GraphOptions(optimizer_options=optimizer_options)
  config = tf.ConfigProto(graph_options=graph_options,
                          intra_op_parallelism_threads=10,
                          inter_op_parallelism_threads=10)

host = "127.0.0.1"
def cluster_spec():
  cluster = {"worker": [host+":"+FLAGS.port0, host+":"+FLAGS.port1]}
  return tf.train.ClusterSpec(cluster).as_cluster_def()

def create_graph(device0, device1, use_gpu=False):
  tf.reset_default_graph()
  dtype=tf.int32
  params_size = 250*1000*FLAGS.data_mb # 1MB is 250k integers
  
  with tf.device(device0):
    var1 = tf.get_variable("var1", [params_size], dtype,
                           initializer=tf.ones_initializer())
  with tf.device(device1):
    var2 = tf.get_variable("var2", [params_size], dtype,
                           initializer=tf.ones_initializer())
  add_op = var1.assign_add(var2)
    
  init_op = tf.global_variables_initializer()
  return init_op, add_op


def run_benchmark(sess, init_op, add_op):
  sess.run(init_op)
  for _ in range(10):
    sess.run(add_op.op)  
  start_time = time.time()
  for i in range(FLAGS.iters):
    sess.run(add_op.op)
    
  elapsed_time = time.time() - start_time
  return float(FLAGS.iters)*FLAGS.data_mb/elapsed_time

def create_done_queue(i):
  with tf.device("/job:worker/task:%s" % (i)):
    return tf.FIFOQueue(1, tf.int32, shared_name="done_queue"+
                        str(i))


def run_benchmark_local():
  ops = create_graph(None, None)
  sess = tf.Session(config=session_config())
  return run_benchmark(sess, *ops)


def run_benchmark_distributed():  
  if FLAGS.use_gpu:
    ops = create_graph("/job:worker/task:0/gpu:0", "/job:worker/task:1/gpu:1")
  else:
    ops = create_graph("/job:worker/task:0", "/job:worker/task:1")
  queues = [create_done_queue(0), create_done_queue(1)]

  port0, port1 = [portpicker.pick_unused_port() for _ in range(2)]
  flags = " ".join(sys.argv)  # pass parent flags to children
  
  def run_worker(w):
    my_env = os.environ.copy()
    if not FLAGS.verbose:
      #my_env["CUDA_VISIBLE_DEVICES"] = ""
      my_env["TF_CPP_MIN_LOG_LEVEL"] = "2"
    if FLAGS.profile:
      my_env["LD_PRELOAD"]="/usr/lib/libtcmalloc_and_profiler.so.4"
      my_env["CPUPROFILE"]="/tmp/profile.out.%s"%(w)
    cmd = "python %s --task=%d --port0=%s --port1=%s"%(flags, w, port0, port1)
    subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT,
                     env=my_env)
    
  run_worker(0)
  run_worker(1)

  sess = tf.Session("grpc://%s:%s"%(host, port0), config=session_config())
  rate = run_benchmark(sess, *ops)

  # bring down workers
  if FLAGS.verbose:
    print("Killing workers.")
  sess.run(queues[1].enqueue(1))
  sess.run(queues[0].enqueue(1))  # bring down master last
  
  return rate

if __name__=='__main__':
  if not FLAGS.task_index:
    rate1 = run_benchmark_local()
    rate2 = run_benchmark_distributed()

    if FLAGS.verbose:
      print("Adding data in %d MB chunks" %(FLAGS.data_mb))
    print("Local rate:       %.2f MB/s" %(rate1,))
    print("Distributed rate: %.2f MB/s" %(rate2,))

  else: # Launch TensorFlow server
    server = tf.train.Server(cluster_spec(), config=session_config(),
                             job_name="worker",
                             task_index=int(FLAGS.task_index))
    queue = create_done_queue(FLAGS.task_index)
    sess = tf.Session(server.target, config=session_config())
    sess.run(queue.dequeue())
    time.sleep(1) # give chance for master session.run call to return
    if FLAGS.verbose:
      print("Worker %s quitting." %(FLAGS.task_index))
