# Dataset Source & Access Instructions

## Source used

| | |
|---|---|
| **Name** | Student Performance (UCI Machine Learning Repository, dataset id 320) |
| **Authors** | Paulo Cortez, Alice Silva - University of Minho, Portugal |
| **Citation** | P. Cortez and A. Silva. *Using Data Mining to Predict Secondary School Student Performance.* Proceedings of 5th FUture BUsiness TEChnology Conference (FUBUTEC 2008), pp. 5-12, Porto, Portugal, 2008. |
| **Page** | https://archive.ics.uci.edu/dataset/320/student+performance |
| **Download URL used by the pipeline** | https://archive.ics.uci.edu/static/public/320/student+performance.zip |
| **Licence** | Creative Commons Attribution 4.0 (CC BY 4.0), free and public |
| **Files** | `student-mat.csv` (Mathematics, 395 rows) and `student-por.csv` (Portuguese, 649 rows); 33 columns each; `;` separated |
| **Privacy** | Fully anonymised. No names or ids; only coded demographic attributes. No personal data is added by this project. |

The zip contains a second zip (`student.zip`) with the two CSV files, the column description (`student.txt`) and the authors' R script for matching students across both files (`student-merge.R`).

## How to access it

**Automatically (recommended):** the pipeline downloads it on every run.

```bash
make pipeline        # or: python -m src.pipeline
```

The download, unzip, a raw copy in `data/raw/<run_id>/`, the row counts and checksums all happen in `src/ingestion/ingest.py`.

**Manually:** open the dataset page above, click **Download**, and unzip.

**Offline:** download the zip once and point the pipeline to it:

```bash
export UCI_LOCAL_ZIP=/path/to/student+performance.zip
make pipeline
```

## Why only this source

The brief names UCI as the *primary* dataset. Kaggle, ERP and LMS sources are listed as *optional*. This project uses only the UCI data, so every record is real, public and legally usable.

The two UCI files act as two sources: one per subject. Many students appear in both, which is why the pipeline has a student-id standardisation step (see `data_dictionary.md` §3).

**Limitations to keep in mind**
- UCI gives a yearly absence count, not session-level attendance. Attendance % therefore assumes 120 sessions per subject per year (configurable).
- There are no assignment-submission records, so an "assignment completion rate" feature is not available.
- G1, G2 and G3 are used as the three assessment terms (Period 1, Period 2, Final).
