
(function () {
    function initSkillPickers() {
        const dataEl = document.getElementById('skill-groups-data');
        if (!dataEl) return;
        const skillGroups = JSON.parse(dataEl.textContent);

        const skillNameById = {};
        skillGroups.forEach(function (group) {
            group.skills.forEach(function (skill) {
                skillNameById[skill.id] = skill.name;
            });
        });

        document.querySelectorAll('.skill-picker').forEach(function (picker) {
            const fieldId = picker.dataset.fieldId;
            const select = document.getElementById(fieldId);
            if (!select) return;

            const button = picker.querySelector('.skill-picker-button');
            const buttonText = picker.querySelector('.skill-picker-button-text');
            const panel = picker.querySelector('.skill-picker-panel');
            const searchInput = picker.querySelector('.skill-picker-search');
            const showAllBtn = picker.querySelector('.skill-picker-show-all');
            const resultsEl = picker.querySelector('.skill-picker-results');
            const defaultLabel = buttonText.textContent;

            function syncButtonLabel() {
                const name = skillNameById[select.value];
                buttonText.textContent = name || defaultLabel;
            }

            function renderGroups(filterText) {
                const term = (filterText || '').trim().toLowerCase();
                resultsEl.innerHTML = '';
                let anyMatch = false;

                skillGroups.forEach(function (group) {
                    const courseMatches = term && group.course.toLowerCase().includes(term);
                    const matchingSkills = group.skills.filter(function (skill) {
                        return !term || courseMatches || skill.name.toLowerCase().includes(term);
                    });
                    if (matchingSkills.length === 0) return;
                    anyMatch = true;

                    const groupEl = document.createElement('div');
                    groupEl.className = 'skill-picker-group';

                    const heading = document.createElement('div');
                    heading.className = 'skill-picker-group-heading';
                    heading.textContent = group.course;
                    groupEl.appendChild(heading);

                    matchingSkills.forEach(function (skill) {
                        const item = document.createElement('button');
                        item.type = 'button';
                        item.className = 'skill-picker-item';
                        item.textContent = skill.name;
                        item.addEventListener('click', function () {
                            select.value = skill.id;
                            buttonText.textContent = skill.name;
                            closePanel();
                        });
                        groupEl.appendChild(item);
                    });

                    resultsEl.appendChild(groupEl);
                });

                if (!anyMatch) {
                    const empty = document.createElement('div');
                    empty.className = 'skill-picker-empty';
                    empty.textContent = 'No matching skills or courses.';
                    resultsEl.appendChild(empty);
                }
            }

            function openPanel() {
                panel.hidden = false;
                searchInput.value = '';
                resultsEl.innerHTML = '';
                searchInput.focus();
            }

            function closePanel() {
                panel.hidden = true;
            }

            button.addEventListener('click', function (e) {
                e.preventDefault();
                if (panel.hidden) {
                    openPanel();
                } else {
                    closePanel();
                }
            });

            showAllBtn.addEventListener('click', function () {
                renderGroups('');
            });

            searchInput.addEventListener('input', function () {
                renderGroups(searchInput.value);
            });

            document.addEventListener('click', function (e) {
                if (!picker.contains(e.target)) {
                    closePanel();
                }
            });

            syncButtonLabel();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSkillPickers);
    } else {
        initSkillPickers();
    }
})();