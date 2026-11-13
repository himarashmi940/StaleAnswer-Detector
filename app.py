
import streamlit as st

from claim_extractor import ClaimExtractionError, extract_claims
from web_research import research_claim
from answer_verifier import ClaimVerificationError, verify_claim
from bifrost_client import ModelResponseError
from pdf_generator import generate_pdf


st.set_page_config(
    page_title="Stale-Answer Detector",
    page_icon="🔎",
    layout="wide",
)

st.title("🔎 Stale-Answer Detector")
st.subheader("Check whether AI-generated answers are still up to date.")

st.write(
    "Paste an AI-generated answer below. "
    "Our system will extract factual claims, search current web sources "
    "and assess their accuracy and freshness."
)

answer = st.text_area(
    "Enter your AI-generated answer",
    height=220,
    placeholder="Paste your answer here..."
)


def calculate_freshness_score(results):

    weights = {
        "Verified": 100,
        "Potentially outdated": 50,
        "Conflicting": 0,
        "Unable to verify": 25
    }

    if not results:
        return 0

    total = sum(weights.get(item.get("status"), 25) for item in results)

    return round(total / len(results))


if st.button("Check Answer", type="primary"):

    if not answer.strip():
        st.warning("Please enter an answer first.")

    else:
        results = []

        try:
            with st.spinner("Extracting factual claims..."):
                try:
                    claims = extract_claims(answer)
                except (ClaimExtractionError, ModelResponseError, ValueError) as error:
                    st.error(f"Claim extraction failed: {error}")
                    st.stop()
                except Exception as error:
                    st.error(
                        "Claim extraction failed "
                        f"({type(error).__name__}). Please try again."
                    )
                    st.stop()

            if not claims:
                st.warning("No factual claims were identified.")
                st.stop()

            st.success(f"Extracted {len(claims)} factual claims.")

            for index, claim in enumerate(claims, start=1):
                with st.spinner("Researching current information..."):
                    try:
                        research = research_claim(claim)
                    except (RuntimeError, ValueError) as error:
                        research = {
                            "claim": claim,
                            "sources": [],
                            "error": str(error),
                        }
                        st.warning(f"Web research failed: {error}")
                    except Exception as error:
                        research_error = (
                            "An unexpected error occurred "
                            f"({type(error).__name__})."
                        )
                        research = {
                            "claim": claim,
                            "sources": [],
                            "error": research_error,
                        }
                        st.warning(f"Web research failed: {research_error}")

                with st.spinner("Verifying claim..."):
                    try:
                        verification = verify_claim(claim, research)
                    except (
                        ClaimVerificationError,
                        ModelResponseError,
                        ValueError,
                    ) as error:
                        st.error(f"Claim verification failed: {error}")
                        st.stop()
                    except Exception as error:
                        st.error(
                            "Claim verification failed "
                            f"({type(error).__name__}). Please try again."
                        )
                        st.stop()

                verification["sources"] = research.get("sources", [])
                results.append(verification)

                status = verification.get(
                    "status", "Unable to verify"
                )

                with st.expander(f"Claim {index}: {claim}", expanded=True):
                    st.markdown(f"**Status:** `{status}`")
                    st.write(
                        "**Explanation:** "
                        + verification.get("explanation", "")
                    )
                    st.write(
                        "**Freshness:** "
                        + verification.get("freshness_note", "")
                    )
                    if research.get("error"):
                        st.warning(research["error"])
                    st.write("**Sources:**")
                    sources = research.get("sources", [])
                    if sources:
                        for source in sources:
                            if source.get("url"):
                                st.link_button(
                                    source.get("title") or "Open source",
                                    source["url"],
                                )
                                if source.get("content"):
                                    st.caption(source["content"])
                    else:
                        st.write("No sources found.")

            score = calculate_freshness_score(results)

            st.subheader("Overall Freshness Score")

            st.metric(
                label="Freshness Score",
                value=f"{score}/100"
            )

            st.progress(score / 100)

            st.caption(
                "This is a simple heuristic based on verification "
                "statuses, not a probability that the answer is true."
            )

            pdf_data = generate_pdf(results, freshness_score=score)

            st.download_button(
                label="Download Verification Report (PDF)",
                data=pdf_data,
                file_name="Stale_Answer_Report.pdf",
                mime="application/pdf"
            )

            st.success("Answer verification completed!")

        except (ModelResponseError, RuntimeError, ValueError) as error:
            st.error(str(error))
        except Exception as error:
            st.error(
                "The verification workflow could not be completed "
                f"({type(error).__name__}). Check the Bifrost and Tavily "
                "configuration, then try again."
            )
