# option-scripts

A collection of python scripts to backtest / simulate option strategies.

## Setup

Install conda:
```
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
bash miniconda.sh -b -p $HOME/miniconda
$HOME/miniconda/bin/conda init
source ~/.bashrc
```

Set up conda env:
```
conda create -n pantheon python=3.12 numpy matplotlib
conda activate pantheon
```

## Scripts

Run backtest:
```
./run.sh
```
