vknotifier
==========

App for notification of changing online statuses for specific users on vk.com

Description
----------

vknotifier is an application for those who need to monitor online status of specific users on social network vk.com. It just sits in your system tray and displays notifications when someone from a specific set of users becomes online or offline.

vknotifier currently works only on Windows.

![](https://raw.github.com/Fatal1ty/trash/master/vknotifier/vknotifier.png)

Getting started
----------

Install [vk package](https://github.com/Fatal1ty/vk) first.

In `settings.ini` specify list of user ids (uids):

```
    "users": [1, 2]
```

and checking interval in seconds:

```
    "delay": 5
```

And start vknotifier:

```
    pythonw.exe vknotifier.py
```
