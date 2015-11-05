#! /usr/bin/env python
# __author__ = 'Will'
import hashlib
import hmac
import math
import random
import string

_rng = random.SystemRandom()
ALPHANUMERIC = string.letters + string.digits

def generate_random_string(length=None, entropy=None, pool=ALPHANUMERIC):
    """Generates a random string using the given sequence pool.

    To generate stronger passwords, use ASCII_PRINTABLE as pool.

    Entropy is:

         H = log2(N**L)

    where:

    - H is the entropy in bits.
    - N is the possible symbol count
    - L is length of string of symbols

    Entropy chart::

        -----------------------------------------------------------------
        Symbol set              Symbol Count (N)  Entropy per symbol (H)
        -----------------------------------------------------------------
        HEXADECIMAL_DIGITS      16                4.0000 bits
        DIGITS                  10                3.3219 bits
        LOWERCASE_ALPHA         26                4.7004 bits
        UPPERCASE_ALPHA         26                4.7004 bits
        PUNCTUATION             32                5.0000 bits
        LOWERCASE_ALPHANUMERIC  36                5.1699 bits
        UPPERCASE_ALPHANUMERIC  36                5.1699 bits
        ALPHA                   52                5.7004 bits
        ALPHANUMERIC            62                5.9542 bits
        ASCII_PRINTABLE         94                6.5546 bits
        ALL_PRINTABLE           100               6.6438 bits

    :param length:
        The length of the random sequence. Use this or `entropy`, not both.
    :param entropy:
        Desired entropy in bits. Use this or `length`, not both.
        Use this to generate passwords based on entropy:
        http://en.wikipedia.org/wiki/Password_strength
    :param pool:
        A sequence of characters from which random characters are chosen.
        Default to case-sensitive alpha-numeric characters.
    :returns:
        A string with characters randomly chosen from the pool.
    """
    pool = list(set(pool))

    if length and entropy:
        raise ValueError('Use length or entropy, not both.')

    if length <= 0 and entropy <= 0:
        raise ValueError('Length or entropy must be greater than 0.')

    if entropy:
        log_of_2 = 0.6931471805599453
        length = long(math.ceil((log_of_2 / math.log(len(pool))) * entropy))

    return ''.join(_rng.choice(pool) for _ in xrange(length))

def generate_password_hash(password, method='sha1', length=22, pepper=None):
    """Hashes a password.

    The format of the string returned includes the method that was used
    so that :func:`check_password_hash` can check the hash.

    This method can **not** generate unsalted passwords but it is possible
    to set the method to plain to enforce plaintext passwords. If a salt
    is used, hmac is used internally to salt the password.

    :param password:
        The password to hash.
    :param method:
        The hash method to use (``'md5'`` or ``'sha1'``).
    :param length:
        Length of the salt to be created.
    :param pepper:
        A secret constant stored in the application code.
    :returns:
        A formatted hashed string that looks like this::

            method$salt$hash

    This function was ported and adapted from `Werkzeug`_.
    """
    salt = method != 'plain' and generate_random_string(length) or ''
    hashval = hash_password(password, method, salt, pepper)
    if hashval is None:
        raise TypeError('Invalid method %r.' % method)

    return '%s$%s$%s' % (hashval, method, salt)

def hash_password(password, method, salt=None, pepper=None):
    """Hashes a password.

    Supports plaintext without salt, unsalted and salted passwords. In case
    salted passwords are used hmac is used.

    :param password:
        The password to be hashed.
    :param method:
        A method from ``hashlib``, e.g., `sha1` or `md5`, or `plain`.
    :param salt:
        A random salt string.
    :param pepper:
        A secret constant stored in the application code.
    :returns:
        A hashed password.

    This function was ported and adapted from `Werkzeug`_.
    """
    password = str(password)
    if method == 'plain':
        return password

    method = getattr(hashlib, method, None)
    if not method:
        return None

    if salt:
        h = hmac.new(str(salt), password, method)
    else:
        h = method(password)

    if pepper:
        h = hmac.new(str(pepper), h.hexdigest(), method)

    return h.hexdigest()

def get_hash_command(hash,new_pwd=""):
  try:
    hashval, method, salt = hash.split('$', 2)
  except:
    print "hash supplied must be escaped - insert a backslash '\\' before dollar signs"
    return
  new_hash =  generate_password_hash(new_pwd, method)
  print "New hash:"
  print  new_hash

if __name__ == '__main__':
  import scriptine
  scriptine.run()