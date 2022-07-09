# push_wechat
一个将打印机状态实时推送到微信的Moonraker插件

![image](https://user-images.githubusercontent.com/31061246/169344514-43e9e7cd-d7a6-425b-a1c7-e82d9a359bba.png)

* 目前功能很少，后面有时间再完善并加入邮件推送

* 注意,企业微信现在需要配置可信IP才能正常使用。
* 如果IP不可信会出现警告ErrCode：60020
* 配置入口：企业微信网页后台->应用管理->企业可信IP 配置

# 安装

```bash
wget https://raw.githubusercontent.com/kluoyun/push_wechat/main/fonts/FreeMono.ttf -O /tmp/FreeMono.ttf
wget https://raw.githubusercontent.com/kluoyun/push_wechat/main/push_wechat.py -O ~/moonraker/moonraker/components/push_wechat.py
sudo systemctl restart moonraker

```

# 配置

* 在moonraker.conf中加入如下配置

```cfg
[push_wechat]
corp_secret: oxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# 企业微信应用私钥
corp_id: wwxxxxxxxxxxxxxxx
# 企业ID
agent_id: 1xxxxxxx
# 企业微信应用ID
to_user: @all
# 接收消息的人
# 消息类型为微信时：企业微信成员ID.@all为所有人.多人使用|分开
# 消息类型为邮件时：xxxx@xxx.xxx.多个接收邮箱用|分开

#mail_host: smtp.xxxx.xxx
# 发信服务器
#mail_user: xxxx@xxxx.xxx
# 发信邮箱
#mail_pass: xxxxxxxxxxxxx
# 发信邮箱密码，QQ邮箱等需要授权码
#mail_port: 25
# smtp发信服务器端口，默认为25

msg_type: wechat
# 消息类型
# 企业微信：wechat, 
# 邮件：mail
```

# 关键参数获取

* 未注册企业微信的请先注册企业微信

1. corp_id获取

扫码进入企业微信后台，获取企业id
https://work.weixin.qq.com/wework_admin/loginpage_wx

![image](https://user-images.githubusercontent.com/31061246/169342247-dfcf3c49-a0a8-4a52-8309-d48ffc4e04d1.png)

2. 创建应用

![1652975439(1)](https://user-images.githubusercontent.com/31061246/169342875-b6bbdcc5-90b2-409b-ae86-a6b63c32f5fc.png)

* 应用信息自行填写

3. agent_id和corp_secret获取

![1652975529(1)](https://user-images.githubusercontent.com/31061246/169343831-1d6304d0-13d9-4b55-8829-86a7507270bd.png)
![1652975619(1)](https://user-images.githubusercontent.com/31061246/169343979-1c5011c5-33a8-4fc1-9b67-07083e0461db.png)

* Secret点击查看后需要在企业微信客户端才能查看

4. 将以上获取到的参数填写到moonraker.conf中保存并重启后即可实时推送打印机状态到微信
