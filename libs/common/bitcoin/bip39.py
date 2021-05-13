# Mnemonic convertion to seed and to/from bytes
import sys

if sys.implementation.name == "micropython":
    import hashlib
    from micropython import const
else:
    from .util import hashlib, const

try:
    # RAM-optimized c-implementation of wordlist lookup
    from .wordlists.ubip39 import WORDLIST
except:
    # normal python list (for desktop embit)
    from .wordlists.bip39 import WORDLIST

PBKDF2_ROUNDS = const(2048)


def mnemonic_to_bytes(mnemonic: str, ignore_checksum=False):
    # this function is copied from Jimmy Song's HDPrivateKey.from_mnemonic() method

    words = mnemonic.strip().split()
    if len(words) % 3 != 0 or len(words) < 12:
        raise ValueError("Invalid recovery phrase")

    binary_seed = bytearray()
    offset = 0
    for word in words:
        if word not in WORDLIST:
            raise ValueError("Word '%s' is not in the dictionary" % word)
        index = WORDLIST.index(word)
        remaining = 11
        while remaining > 0:
            bits_needed = 8 - offset
            if remaining == bits_needed:
                if bits_needed == 8:
                    binary_seed.append(index)
                else:
                    binary_seed[-1] |= index
                offset = 0
                remaining = 0
            elif remaining > bits_needed:
                if bits_needed == 8:
                    binary_seed.append(index >> (remaining - 8))
                else:
                    binary_seed[-1] |= index >> (remaining - bits_needed)
                remaining -= bits_needed
                offset = 0
                # lop off the top 8 bits
                index &= (1 << remaining) - 1
            else:
                binary_seed.append(index << (8 - remaining))
                offset = remaining
                remaining = 0

    checksum_length_bits = len(words) * 11 // 33
    num_remainder = checksum_length_bits % 8
    if num_remainder:
        checksum_length = checksum_length_bits // 8 + 1
        bits_to_ignore = 8 - num_remainder
    else:
        checksum_length = checksum_length_bits // 8
        bits_to_ignore = 0
    raw = bytes(binary_seed)
    data, checksum = raw[:-checksum_length], raw[-checksum_length:]
    computed_checksum = bytearray(hashlib.sha256(data).digest()[:checksum_length])

    # ignore the last bits_to_ignore bits
    computed_checksum[-1] &= 256 - (1 << (bits_to_ignore + 1) - 1)
    if not ignore_checksum and checksum != bytes(computed_checksum):
        raise ValueError("Checksum verification failed")
    return data


def mnemonic_is_valid(mnemonic: str):
    """Checks if mnemonic is valid (checksum and words)"""
    try:
        mnemonic_to_bytes(mnemonic)
        return True
    except:
        return False


def mnemonic_to_seed(mnemonic: str, password: str = ""):
    # first we try to conver mnemonic to bytes
    # and raise a correct error if it is invalid
    mnemonic_to_bytes(mnemonic)
    # from hashlib.c usermodule
    # mp_obj_t password, mp_obj_t salt, mp_obj_t iterations, mp_obj_t len
    return hashlib.pbkdf2_hmac(
        "sha512",
        mnemonic.encode("utf-8"),
        ("mnemonic" + password).encode("utf-8"),
        PBKDF2_ROUNDS,
        64,
    )


def _extract_index(bits, b, n):
    value = 0
    for pos in range(n * bits, (n + 1) * bits):
        value = value << 1
        if b[pos // 8] & (1 << (7 - pos % 8)):
            value += 1
    return value


def mnemonic_from_bytes(b):
    if len(b) % 4 != 0:
        raise ValueError("Byte array should be multiple of 4 long (16, 20, ..., 32)")
    total_bits = len(b) * 8
    checksum_bits = total_bits // 32
    total_mnemonics = (total_bits + checksum_bits) // 11
    # no need to truncate checksum - we already know total_mnemonics
    checksum = bytearray(hashlib.sha256(b).digest())
    b += checksum
    mnemonic = []
    for i in range(0, total_mnemonics):
        idx = _extract_index(11, b, i)
        mnemonic.append(WORDLIST[idx])
    return " ".join(mnemonic)


def find_candidates(word_part, nmax=5):
    candidates = []
    for w in WORDLIST:
        if w.startswith(word_part):
            candidates.append(w)
        if len(candidates) >= nmax:
            break
    return candidates
