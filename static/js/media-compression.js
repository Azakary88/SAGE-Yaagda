(function () {
    const MAX_UPLOAD_SIZE = 2 * 1024 * 1024;
    const TARGET_SIZE = 1800 * 1024;
    const MAX_DIMENSION = 1600;
    const QUALITY_STEPS = [0.85, 0.75, 0.65, 0.55, 0.45];

    function formatSize(bytes) {
        return (bytes / (1024 * 1024)).toFixed(1) + ' Mo';
    }

    function imageInputFields() {
        return Array.from(document.querySelectorAll('input[type="file"]')).filter(function (input) {
            return (input.accept || '').toLowerCase().includes('image');
        });
    }

    function statusNodeFor(input) {
        let node = input.parentElement.querySelector('[data-media-compression-status]');
        if (!node) {
            node = document.createElement('div');
            node.className = 'form-text text-muted';
            node.setAttribute('data-media-compression-status', '');
            input.insertAdjacentElement('afterend', node);
        }
        return node;
    }

    function loadImage(file) {
        return new Promise(function (resolve, reject) {
            const image = new Image();
            const url = URL.createObjectURL(file);

            image.onload = function () {
                URL.revokeObjectURL(url);
                resolve(image);
            };
            image.onerror = function () {
                URL.revokeObjectURL(url);
                reject(new Error("L'image n'a pas pu être lue."));
            };
            image.src = url;
        });
    }

    function scaledDimensions(width, height) {
        const largestSide = Math.max(width, height);
        if (largestSide <= MAX_DIMENSION) {
            return { width: width, height: height };
        }

        const ratio = MAX_DIMENSION / largestSide;
        return {
            width: Math.round(width * ratio),
            height: Math.round(height * ratio),
        };
    }

    function canvasToBlob(canvas, quality) {
        return new Promise(function (resolve) {
            canvas.toBlob(resolve, 'image/jpeg', quality);
        });
    }

    async function compressImage(file) {
        const image = await loadImage(file);
        const dimensions = scaledDimensions(image.naturalWidth, image.naturalHeight);
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');

        canvas.width = dimensions.width;
        canvas.height = dimensions.height;
        context.fillStyle = '#ffffff';
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0, dimensions.width, dimensions.height);

        let bestBlob = null;
        for (const quality of QUALITY_STEPS) {
            const blob = await canvasToBlob(canvas, quality);
            if (!blob) {
                continue;
            }
            bestBlob = blob;
            if (blob.size <= TARGET_SIZE) {
                break;
            }
        }

        if (!bestBlob || bestBlob.size >= file.size) {
            return file;
        }

        const originalName = file.name.replace(/\.[^.]+$/, '');
        return new File([bestBlob], originalName + '.jpg', {
            type: 'image/jpeg',
            lastModified: Date.now(),
        });
    }

    function replaceSelectedFile(input, file) {
        const files = new DataTransfer();
        files.items.add(file);
        input.files = files.files;
    }

    async function prepareForm(form) {
        const inputs = imageInputFields().filter(function (input) {
            return input.form === form && input.files && input.files.length === 1;
        });

        for (const input of inputs) {
            const file = input.files[0];
            const status = statusNodeFor(input);

            if (!file.type.startsWith('image/')) {
                continue;
            }

            if (file.size <= MAX_UPLOAD_SIZE) {
                status.textContent = 'Image prête pour l’envoi (' + formatSize(file.size) + ').';
                continue;
            }

            status.textContent = 'Compression de l’image avant l’envoi...';
            const compressed = await compressImage(file);
            replaceSelectedFile(input, compressed);

            if (compressed.size <= MAX_UPLOAD_SIZE) {
                status.textContent = 'Image compressée : ' + formatSize(file.size) + ' -> ' + formatSize(compressed.size) + '.';
            } else {
                status.textContent = 'Image encore lourde après compression (' + formatSize(compressed.size) + '). Elle peut être refusée.';
            }
        }
    }

    document.addEventListener('change', function (event) {
        const input = event.target;
        if (!(input instanceof HTMLInputElement) || input.type !== 'file' || !input.files.length) {
            return;
        }

        if (!(input.accept || '').toLowerCase().includes('image')) {
            return;
        }

        const file = input.files[0];
        const status = statusNodeFor(input);
        if (file.size > MAX_UPLOAD_SIZE) {
            status.textContent = 'Cette image sera compressée avant l’envoi (' + formatSize(file.size) + ').';
        } else {
            status.textContent = 'Image prête pour l’envoi (' + formatSize(file.size) + ').';
        }
    });

    document.addEventListener('submit', async function (event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || form.dataset.mediaCompressionReady === '1') {
            return;
        }

        const hasImageInput = imageInputFields().some(function (input) {
            return input.form === form && input.files && input.files.length === 1;
        });

        if (!hasImageInput) {
            return;
        }

        event.preventDefault();
        const submitter = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitter) {
            submitter.disabled = true;
            submitter.dataset.originalText = submitter.textContent;
            submitter.textContent = 'Préparation...';
        }

        try {
            await prepareForm(form);
            form.dataset.mediaCompressionReady = '1';
            form.submit();
        } catch (error) {
            const inputs = imageInputFields().filter(function (input) {
                return input.form === form;
            });
            inputs.forEach(function (input) {
                statusNodeFor(input).textContent = "L'image n'a pas pu être compressée automatiquement.";
            });
            if (submitter) {
                submitter.disabled = false;
                submitter.textContent = submitter.dataset.originalText || 'Envoyer';
            }
        }
    });
}());
