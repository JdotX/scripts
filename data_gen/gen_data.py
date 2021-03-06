# Generate spark-level data
# For Chukonu evaluation

import random, math, sys, time

def gen_single_data_piece(feature_no, step):
    ans = ""
    feature_set = []
    a = []
    # decide the class
    y = random.randint(0,1)
    '''
    # generate the 4 first features
    for i in [1,2,3,4]:
        a.append(random.random())
    ym = a[0]+2*a[1]-2*a[2]-a[3]
    if ym > 0:
        y = 1
    else:
        y = 0
    '''
    ans = ans + str(y) + " "    
    sample_feature = 0
    while sample_feature < feature_no:
        feature_set.append(sample_feature)
        sample_feature = sample_feature + random.randint(1, step) + step
    '''
    for ft in [1,2,3,4]:
        ans = ans + str(ft) + ":" + str(a[ft-1]) + " "
    '''
    for ft in feature_set:
        sp = random.random()
        ans = ans + str(ft) + ":" + str(sp) + " "
    ans = ans + "\n"
    return ans


def gen_data_and_write(sample_no, feature_no, output_txt_path, step_size = 2000):
    f = open(output_txt_path, 'w')
    for i in range(sample_no):
        if i % 1 == 0:
            print (i)
        str_to_write = gen_single_data_piece(feature_no, step_size)
        f.write(str_to_write)
    f.close()
    return


if __name__ == '__main__':
    t1 = time.time()
    sample_no = 100
    feature_no = 200000000
    output_txt_path = "synthetic_lr_data2.txt"
    gen_data_and_write(sample_no, feature_no, output_txt_path)
    print time.time() - t1
