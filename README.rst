``fbchat`` - Facebook Messenger for Python
==========================================

.. image:: https://badgen.net/pypi/v/fbchat-asyncio
    :target: https://pypi.python.org/pypi/fbchat-asyncio
    :alt: Project version

.. image:: https://badgen.net/badge/python/3.6,3.7,3.8?list=|
    :target: https://pypi.python.org/pypi/fbchat-asyncio
    :alt: Supported python versions: 3.6, 3.7 and 3.8

.. image:: https://badgen.net/pypi/license/fbchat
    :target: https://github.com/tulir/fbchat-asyncio/tree/master/LICENSE
    :alt: License: BSD 3-Clause

A powerful and efficient library to interact with
`Facebook's Messenger <https://www.facebook.com/messages/>`__, using just your email and password.
This is an asyncio fork of the `fbchat <https://github.com/carpedm20/fbchat>`__ library.

This is *not* an official API, Facebook has that `over here <https://developers.facebook.com/docs/messenger-platform>`__ for chat bots. This library differs by using a normal Facebook account instead.

``fbchat`` currently support:

- Sending many types of messages, with files, stickers, mentions, etc.
- Fetching all messages, threads and images in threads.
- Searching for messages and threads.
- Creating groups, setting the group emoji, changing nicknames, creating polls, etc.
- Listening for, an reacting to messages and other events in real-time.
- Type hints, and it has a modern codebase (e.g. only Python 3.5 and upwards).
- ``async``/``await`` (COMING).

Essentially, everything you need to make an amazing Facebook bot!


Caveats
-------

``fbchat`` works by imitating what the browser does, and thereby tricking Facebook into thinking it's accessing the website normally.

However, there's a catch! **Using this library may not comply with Facebook's Terms Of Service!**, so be responsible Facebook citizens! We are not responsible if your account gets banned!

Additionally, **the APIs the library is calling is undocumented!** In theory, this means that your code could break tomorrow, without the slightest warning!
If this happens to you, please report it, so that we can fix it as soon as possible!

.. inclusion-marker-intro-end
.. This message doesn't make sense in the docs at Read The Docs, so we exclude it

With that out of the way, you may go to `Read The Docs <https://fbchat.readthedocs.io/>`__ to see the full documentation!

.. inclusion-marker-installation-start


Installation
------------

.. code-block::

    $ pip install fbchat-asyncio

If you don't have `pip <https://pip.pypa.io/>`_, `this guide <http://docs.python-guide.org/en/latest/starting/installation/>`_ can guide you through the process.

You can also install directly from source, provided you have ``pip>=19.0``:

.. code-block::

    $ pip install git+https://github.com/tulir/fbchat-asyncio.git#egg=fbchat

.. inclusion-marker-installation-end


Examples
--------

All examples are available `here <https://github.com/tulir/fbchat-asyncio/tree/master/examples>`__.

Basic example: `basic_usage.py <https://github.com/tulir/fbchat-asyncio/blob/master/examples/basic_usage.py>`__

If login using email and password doesn't work, you can create a file in the working directory called "session.json" with the following format:

.. code-block:: json

	{
		"c_user": "[15 digits]",
		"xs": "[variable]"
	}

These values are from the cookies stored by your browser after logging in your account. You can get these values this way:

On Firefox:

1. Open `messenger.com <https://messenger.com>`__, login and press F12
2. Go to "Storage"
3. Go to "Cookies"
4. Select "https://messenger.com" and copy the values from there.

On Chrome:

The process is the same, the only difference is "Storage" is called "Application" in Chrome.

**KEEP IN MIND: These values can be used by someone else to login to your account, so keep them private!**

After that you can use this code: `session_handling.py <https://github.com/tulir/fbchat-asyncio/blob/master/examples/session_handling.py>`__

Depending on the domain you're logging into, you have to set the "domain" argument appropriately (either `facebook.com` or `messenger.com`). Here's an example:

.. code-block:: python

	await fbchat.Session.from_cookies(cookies, domain="messenger.com")

Maintainer
----------

- Tulir Asokan / `@tulir <https://github.com/tulir>`__


Acknowledgements
----------------

This project was originally inspired by `facebook-chat-api <https://github.com/Schmavery/facebook-chat-api>`__.
