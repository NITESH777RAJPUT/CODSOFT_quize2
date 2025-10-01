// JavaScript for Online Quiz Maker
async function fetchQuizData(quizId) {
    const res = await fetch(`/api/quiz/${quizId}/data`);
    return res.json();
}

if (typeof QUIZ_ID !== 'undefined') {
    (async () => {
        const data = await fetchQuizData(QUIZ_ID);
        const questions = data.questions;
        let idx = 0;
        const answers = {};

        const qWrap = document.getElementById('questionWrap');
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');
        const submitBtn = document.getElementById('submitBtn');

        function render() {
            const q = questions[idx];
            qWrap.innerHTML = `<div class="qcard"><h3>Question ${idx + 1} / ${questions.length}</h3><p>${q.text}</p>
        <ul class="choices">` + q.choices.map(c => `<li><label><input type="radio" name="q_${q.id}" value="${c.id}" ${answers[q.id] == c.id ? 'checked' : ''}> ${c.text}</label></li>`).join('') + `</ul></div>`;
            prevBtn.style.display = idx === 0 ? 'none' : '';
            nextBtn.style.display = idx === questions.length - 1 ? 'none' : '';
            submitBtn.style.display = idx === questions.length - 1 ? '' : 'none';
            q.choices.forEach(c => {
                const sel = document.querySelector(`input[name='q_${q.id}'][value='${c.id}']`);
                sel.addEventListener('change', () => { answers[q.id] = c.id; });
            });
        }

        prevBtn.addEventListener('click', () => { if (idx > 0) { idx--; render(); } });
        nextBtn.addEventListener('click', () => { if (idx < questions.length - 1) { idx++; render(); } });
        submitBtn.addEventListener('click', async () => {
            const payload = { answers: answers };
            const res = await fetch(`/api/quiz/${QUIZ_ID}/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await res.json();
            qWrap.innerHTML = `<h3>Your score: ${result.score} / ${result.total}</h3>` + result.details.map(d => `<div class="result-item"><p><strong>${d.question}</strong></p><p>Your answer: ${d.chosen || '<em>Not answered</em>'}</p><p>Correct: ${d.correct}</p><p>${d.is_correct ? '<span class="ok">Correct</span>' : '<span class="bad">Wrong</span>'}</p></div>`).join('');
            prevBtn.style.display = 'none'; nextBtn.style.display = 'none'; submitBtn.style.display = 'none';
        });

        render();
    })();
}
