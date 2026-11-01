# Numerical boundary observation before repair

Recovered source: staged c43b6885, applied above e73e9478.
Command: NumPy encode/decode with Python warnings promoted to errors.

- 1x24 float64 values 1e100: RuntimeWarning overflow encountered in cast.
- 256x24 float32 values 1e20: RuntimeWarning overflow encountered in multiply.
- 256x24 float32 values 1e-30: finite decode, all values zero.

These are record-owner defects; the accepted B14.1 direction codec already uses
FP64 norm accumulation. No production attention/learner caller consumes records.
Publication is held pending red/green numeric proof and fresh EGM.
