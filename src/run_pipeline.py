"""Run the whole data pipeline in order: extract -> clean -> load to MySQL."""
import extract
import clean
import load_mysql

if __name__ == "__main__":
    extract.extract()
    clean.clean()
    load_mysql.main()
    print("\nDone. Next: open notebooks/UrbanPulse_EDA_and_Analysis.ipynb, "
          "then run: streamlit run app/streamlit_app.py")
