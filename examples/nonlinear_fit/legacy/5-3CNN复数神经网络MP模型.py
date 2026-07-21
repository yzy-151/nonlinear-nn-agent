# -*- coding: utf-8 -*-
"""
Created on Tue Aug  6 17:16:53 2024

对应短期学习5.3
修改为复数形式的神经网络
并更换不同的优化器测试性能
可以将不同的数据存入excel中

@author: yzy
"""
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import scipy.io as scio
import torch.nn.functional as F
import matplotlib.pyplot as plt
import pandas as pd
#%%                列举一些激活函数和梯度下降函数

'''
1. optim.SGD (Stochastic Gradient Descent)

    适用条件：适用于大规模数据集和训练任务。它是一种简单而基础的优化方法，适用于一般情况下的模型训练。
    特点：使用固定的学习率，能够处理稀疏数据。通过学习率衰减和动量（momentum）可以提升性能。

2. optim.Adam (Adaptive Moment Estimation)

    适用条件：适用于大多数神经网络任务，尤其是当你不确定最佳学习率时。它结合了 AdaGrad 和 RMSProp 的优点。
    特点：自动调整学习率并使用一阶和二阶矩估计。通常在许多任务中表现良好且稳定。

3. optim.AdamW (Adam with Weight Decay)

    适用条件：适用于需要正则化（如权重衰减）和具有复杂超参数的任务。通常在训练深度神经网络时效果更好。
    特点：与 Adam 相似，但在权重更新时更好地处理了权重衰减，使得正则化更加有效。

4. optim.RMSprop (Root Mean Square Propagation)

    适用条件：适用于非平稳目标（例如，递归神经网络）。对学习率的自适应调整使其在不同尺度的数据上表现良好。
    特点：对每个参数使用不同的学习率。可以应对梯度下降过程中学习率变化较大的情况。

5. optim.Adadelta (Adaptive Delta)

    适用条件：适用于需要避免学习率手动调节的任务。它对学习率进行自适应调整，通常在模型训练中表现稳定。
    特点：扩展了 Adagrad，不再使用固定的学习率，而是使用自适应学习率调整。

6. optim.Adagrad (Adaptive Gradient Algorithm)

    适用条件：适用于稀疏数据任务，如文本和图像分类中的特征向量。对每个参数进行自适应调整，适合处理稀疏特征。
    特点：对每个参数使用不同的学习率，能够有效处理稀疏梯度问题。

7. optim.Nadam (Nesterov-accelerated Adaptive Moment Estimation)

    适用条件：适用于需要 Nesterov 动量的任务。它结合了 Adam 和 Nesterov 动量的优点。
    特点：在动量的基础上结合了自适应学习率，通常能够提高收敛速度和性能。

8. optim.LBFGS (Limited-memory Broyden-Fletcher-Goldfarb-Shanno)

    适用条件：适用于较小规模的数据集或模型，特别是当计算资源允许时。常用于优化有明确目标函数的小型网络。
    特点：基于二阶梯度信息进行优化，比一阶优化方法更为精确，但计算开销较大。

性能比较

不同的优化器在不同任务和数据集上的表现可能有所不同。一般来说：

    Adam 和 AdamW：通常表现优越，适合大多数任务，特别是深度学习任务。
    SGD：简单且高效，但需要精细调整学习率和动量。与动量结合使用时表现良好。
    RMSprop 和 Adadelta：对学习率的自适应调整效果好，但对超参数的选择较敏感。
    Adagrad：适合处理稀疏数据，但学习率可能会过早下降。
    
    
    ####################################激活函数###########################################
    
Sigmoid 和 Tanh：适合小规模网络或二分类问题，适用于输出层或中间层。
ReLU 和其变种 (Leaky ReLU, PReLU, ELU)：适合大多数深层网络，尤其是卷积神经网络中的隐藏层。
Swish：在某些高级应用中表现优越，但计算成本较高。
Softmax：专用于分类任务的输出层。

'''







#%%                     内容


class ComplexConv2d(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, stride=1, padding=1):
        super(ComplexConv2d, self).__init__()
        # 定义实部和虚部的卷积层
        self.conv_real = nn.Conv2d(in_channels, out_channels, kernel_size, stride, padding)#别看跟下一行一样，他们未来的内部权重不一样
        self.conv_imag = nn.Conv2d(in_channels, out_channels, kernel_size, stride, padding)
    
    def forward(self, x_real, x_imag):
        # 实部和虚部分别进行卷积
        real_out = self.conv_real(x_real) - self.conv_imag(x_imag)
        imag_out = self.conv_real(x_imag) + self.conv_imag(x_real)
        return real_out, imag_out

class CNNet(nn.Module):
    def __init__(self):
        super(CNNet, self).__init__()
        self.complex_conv1 = ComplexConv2d(1, 16, kernel_size=3, stride=1, padding=1)
        #如要保持输入输出特征值矩阵一致，应卷积核大小为padding*2+1
        #所以此处的weight数量为3*3*16，bias为16
        self.relu1 = nn.ReLU()
        # self.relu1 = nn.PReLU()
        self.complex_conv2 = ComplexConv2d(16, 32, kernel_size=3, stride=1, padding=1)
        self.relu2 = nn.ReLU()
        # self.relu2 = nn.PReLU()
        self.complex_conv3 = ComplexConv2d(32, 64, kernel_size=3, stride=1, padding=1)
        self.relu3 = nn.ReLU()
        
        # self.relu3 = nn.PReLU()
        self.fc = nn.Linear(64*4*6*2, 2)  # 假设输入到全连接层的特征维度是64*5*6

    def forward(self, x_real, x_imag):
        x_real = x_real.view(-1,1,4,6)
        x_imag = x_imag.view(-1,1,4,6)
        x_real, x_imag = self.complex_conv1(x_real, x_imag)
        x_real = self.relu1(x_real)
        x_imag = self.relu1(x_imag)

        x_real, x_imag = self.complex_conv2(x_real, x_imag)
        x_real = self.relu2(x_real)
        x_imag = self.relu2(x_imag)

        x_real, x_imag = self.complex_conv3(x_real, x_imag)
        x_real = self.relu3(x_real)
        x_imag = self.relu3(x_imag)

        # 展平特征图
        x = torch.cat((x_real, x_imag), dim=1)  # 拼接实部和虚部
        x = x.view(-1, 64*4*6*2)  # 展平，2表示实部和虚部两个通道
        x = self.fc(x)
        return x
def generate_features(X,M):   #初始化特征图
    features = np.zeros((X.size,4*(M+1)),complex)    #输入原始数据，特征图数量为X.size,特征图维度为5*（M+1）
    #将30大小的维度存储在特征图中，看j
    for i in range(M,X.size):        
        for j in range(M+1):
            features[i,j] = X[i-j]#前M个数（M为记忆深度
        for j in range(M+1,2*(M+1)):
            features[i,j] = abs(X[i-(j-M-1)]) ** 1#绝对值
        for j in range(2*(M+1),3*(M+1)):
            features[i,j] = abs(X[i-(j-2*M-2)]) ** 2#绝对值
        for j in range(3*(M+1),4*(M+1)):
            features[i,j] = abs(X[i-(j-3*M-3)]) ** 3#模二次
        # for j in range(M+1):
        #     features[i,j] = X[i-j]#前M个数（M为记忆深度
        # for j in range(M+1,2*(M+1)):
        #     features[i,j] = X[i-(j-M-1)]*abs(X[i-(j-M-1)]) ** 2#绝对值
        # for j in range(2*(M+1),3*(M+1)):
        #     features[i,j] = X[i-(j-2*M-2)]*abs(X[i-(j-2*M-2)]) ** 4#绝对值
        # for j in range(3*(M+1),4*(M+1)):
        #     features[i,j] = X[i-(j-3*M-3)]*abs(X[i-(j-3*M-3)]) ** 6#模二次
            
        # for j in range(4*(M+1),5*(M+1)):
        #     features[i,j] = abs(X[i-(j-4*M-4)]) ** 3#模三次
            # features[i,j] = np.angle(X[i-(j-4*M-4)]) ** 3#模三次
    return features[M:]

def generate_labels(x,M):#生成标签，貌似最后用来和模型输出对比了
    #标签为实部虚部
    labels = np.zeros((x.size,2))
    labels[:,0] = x.real
    labels[:,1] = x.imag
    return labels[M:]

def generate_data():
    #X = np.random.rand(n_samples, *input_shape)
    #y = np.random.rand(n_samples, *output_shape)
    filename = 'C:/Users/yzy/Desktop/华为/python/Simulation_MPDPD_Data.mat'
    matfile = scio.loadmat(filename)
    x = matfile['x'][0]
    d = matfile['d'][0]
    d = d * np.sqrt(np.mean(np.abs(x) ** 2) / np.mean(abs(d) ** 2))   #缩放
    # x_real = np.real(x)
    # x_imag = np.imag(x)
    # train_features_real = generate_features(x_real, M)   #特征图16379*（4*6）
    # train_features_imag = generate_features(x_imag, M)   #特征图16379*（4*6）
    # x_real = np.real(x)
    # x_imag = np.imag(x)
    # train_features_real = generate_features(x_real, M)   #特征图16379*（4*6）
    train_features = generate_features(x, M)   #特征图16379*（4*6）
    train_features_imag = np.imag(train_features)   #特征图16379*（4*6）
    train_features_real = np.real(train_features)   #特征图16379*（4*6）
    train_labels = generate_labels(d, M)#16379*2
    # 将数组转化为pytorch张量,tensor类型
    return torch.from_numpy(train_features_real).float(),torch.from_numpy(train_features_imag).float(), torch.from_numpy(train_labels).float()#浮点类型的训练特征和标签

# 模型训练
M = 5 #记忆长度为五
Nfft = 1024
Fs = 491.52e6
#n_samples = 1000
#input_shape = (16384, 1)
#output_shape = (16384, 1)
lr = 0.01
n_epochs = 500
model = CNNet()
# model = model.cuda()#使用GPU
criterion = nn.MSELoss()#最小均方误差
# criterion = criterion.cuda()
# model.parameters是模型的所有可学习参数，包括权重w和编制bias
optimizer = optim.SGD(model.parameters(), lr=lr)#随机梯度下降(Stochastic Gradient Descent, SGD)算法，学习率为lr
#PyTorch学习率调度器(Learning Rate Scheduler)使用StepLR策略来动态调整优化器的学习率
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.8)#步长10，每隔10个epoch更新一次学习率，方式为*gamma
epoch_loss = np.zeros(505)
for epoch in range(n_epochs):
    #通常在训练循环的末尾调用scheduler.step()来更新学习率。
    scheduler.step()
    running_loss = 0.0
    running_acc = 0.0
    
    X_real, X_imag, y = generate_data()
    # X_real = X_real.cuda()
    # X_imag = X_imag.cuda()
    # y = y.cuda()
    for i in range(16379):
        #初始化梯度为0
        optimizer.zero_grad()
        outputs = model(X_real[i],X_imag[i])#前向传播，计算模型输出
        loss = criterion(outputs, y[i])#计算损失函数（模型输出与真实标签）
        loss.backward()#反向传播，计算梯度
        optimizer.step()#更新模型参数
        running_loss += loss.item()#累加损失值

    epoch_loss[epoch] = running_loss / 16379#计算平均损失

    if epoch % 1 == 0:
        print(f"Epoch: {epoch}, Loss: {epoch_loss[epoch]}")


print('Finished Training')
###############test#############
X_real, X_imag, y = generate_data()
y_hat1 = torch.zeros(16379,2)
for i in range(16379):
    y_hat1[i,:] = model(X_real[i],X_imag[i])
y_hat1 = y_hat1.T
filename = 'C:/Users/yzy/Desktop/华为/python/Simulation_MPDPD_Data.mat'
matfile = scio.loadmat(filename)
x = matfile['x'][0]
d = matfile['d'][0]
d = d * np.sqrt(np.mean(np.abs(x) ** 2) / np.mean(abs(d) ** 2))
y_hat1 = y_hat1[0,:] + 1j*y_hat1[1,:]#到这一步仍然是Tensor数据类型，无法查看
# .detach是从原函数中分理出新张量，再后面转numpy数组
y_hat1 = y_hat1.detach().numpy()
e_fix = d[M:] - y_hat1+x[M:]
AfMPDPD_NMSE = 10*np.log10(np.mean(abs(y_hat1-d[M:])**2)/np.mean(np.abs(d[M:])**2))
#%%                 写进excel
with pd.ExcelWriter('CNN.xlsx', mode='a',engine='openpyxl') as writer: ##mode=a表示添加模式
    # 写入第一个 sheet
    t1 = pd.DataFrame()
    t1['error'] = e_fix
    t1['ep_loss'] = np.hstack((epoch_loss,np.zeros(e_fix.size-epoch_loss.size)))
    t1['NMSE'] = np.hstack((AfMPDPD_NMSE,np.zeros(e_fix.size-AfMPDPD_NMSE.size)))

    t1.to_excel(writer, sheet_name='C_SGD500', index=False)
    # t1.to_excel(writer, sheet_name='C_SGD_gai', index=False)
    
torch.save(model,'C_SGD500.pth')
    # # 写入第二个 sheet
    # t2 = pd.DataFrame()
    # t2['列名1'] = np.random.randn(10)
    # t2['列名2'] = np.random.randint(1, 100, size=10)
    # t2.to_excel(writer, sheet_name='sjsjs2', index=False)
#%%                画图


plt.figure('AFMLPDPD PSD')
plt.title('complex CNN')
plt.psd(x[M:],Nfft,Fs,label='x')
plt.psd(d[M:],Nfft,Fs,label='d')
plt.psd(e_fix,Nfft,Fs,label='e=d-F(x)')
plt.xlabel('Hz')
plt.ylabel('dB')
plt.legend()
plt.show()
torch.save(model,'complexnet_RMSprop_Hardtanh60.pt')

plt.figure(figsize=(8,4))
plt.plot(range(0,60),epoch_loss[0:60])
plt.grid(True)
plt.title('loss')
plt.xlabel('epoch')
plt.ylabel('epoch loss')
plt.legend()
plt.show()


