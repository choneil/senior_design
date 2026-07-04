import * as THREE from 'three';

export class PIPManager {
    constructor(renderer) {
        this.renderer = renderer;
        this.isActive = false;
        this.views = [];
        this.initUI();
        this.initUSBCamera();
    }

    initUI() {
        this.container = document.createElement('div');
        this.container.id = 'pip-sidebar';
        this.container.style.cssText = `
            position: fixed; right: 0; top: 0; width: 240px; height: 100vh;
            background: transparent; border-left: 1px solid #444;
            display: flex; flex-direction: column; gap: 10px; padding: 10px;
            padding-left: 15px; box-sizing: border-box; z-index: 20;
            overflow-y: auto; overflow-x: hidden;
        `;
        document.body.appendChild(this.container);

        const handle = document.createElement('div');
        handle.style.cssText = `position: absolute; left: 0; top: 0; width: 10px; height: 100%; cursor: ew-resize; background: rgba(255, 255, 255, 0.05); z-index: 30;`;
        
        let isResizing = false;
        handle.addEventListener('mousedown', (e) => { isResizing = true; e.preventDefault(); });
        window.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            let newWidth = window.innerWidth - e.clientX;
            newWidth = Math.max(150, Math.min(newWidth, 600));
            this.container.style.width = newWidth + 'px';
        });
        window.addEventListener('mouseup', () => { isResizing = false; });
        this.container.appendChild(handle);
        this.container.addEventListener('mousedown', e => e.stopPropagation());
    }

    createDraggableCard(title) {
        const card = document.createElement('div');
        card.draggable = true;
        card.style.cssText = `
            position: relative; flex: 1; min-height: 100px;
            border: 2px solid rgba(255, 255, 255, 0.5);
            box-sizing: border-box; background: transparent;
            cursor: grab; border-radius: 4px; overflow: hidden;
        `;

        const header = document.createElement('div');
        header.style.cssText = `
            display: flex; justify-content: space-between; align-items: center;
            background: rgba(0, 0, 0, 0.85); padding: 2px 5px;
        `;

        const label = document.createElement('div');
        label.style.cssText = `color: #7fc97f; font-size: 10px; font-family: monospace;`;
        label.innerText = title;

        const select = document.createElement('select');
        select.style.cssText = `font-size: 9px; background: #222; color: #fff; border: none;`;
        select.innerHTML = `<option value="on">Show</option><option value="off">Hide</option>`;
        select.onchange = (e) => { card.style.display = (e.target.value === 'on') ? 'flex' : 'none'; };
        select.onclick = (e) => e.stopPropagation();

        header.appendChild(label);
        header.appendChild(select);
        card.appendChild(header);

        card.ondragstart = (e) => { card.style.opacity = '0.5'; card.classList.add('dragging'); };
        card.ondragend = () => { card.style.opacity = '1'; card.classList.remove('dragging'); };
        card.ondragover = (e) => {
            e.preventDefault();
            const dragging = this.container.querySelector('.dragging');
            if (dragging === card || !dragging) return;
            const bounding = card.getBoundingClientRect();
            if (e.clientY - bounding.top > bounding.height / 2) card.after(dragging);
            else card.before(dragging);
        };

        this.container.appendChild(card);
        return card;
    }

    async initUSBCamera() {
        const card = this.createDraggableCard('USB CAMERA [LIVE]');
        card.style.background = '#000';
        const video = document.createElement('video');
        video.autoplay = true; video.playsInline = true;
        video.style.cssText = `width: 100%; height: 100%; object-fit: cover;`;
        card.appendChild(video);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            video.srcObject = stream;
        } catch (err) { card.innerText = "Camera Unavailable"; }
        
        this.views.push({ name: 'USB', card: card, isVideo: true, video: video });
    }

    attachCameras(robot, ...names) {
        names.forEach(name => {
            const targetLink = robot.links[name];
            if (targetLink) {
                const card = this.createDraggableCard(name);
                const cam = new THREE.PerspectiveCamera(45, 1, 0.001, 10);
                
                // Add a local "Headlight" to this camera to fix dimness
                const headlight = new THREE.PointLight(0xffffff, 4.0);
                cam.add(headlight); 
                
                this.views.push({
                    name: name,
                    camera: cam,
                    target: targetLink,
                    card: card
                });
            }
        });
        this.isActive = true;
    }

    render(scene, innerWidth, innerHeight) {
        if (!this.isActive) return;
        this.renderer.setScissorTest(true);

        this.views.forEach(view => {
            if (view.card.style.display !== 'none' && view.card.getBoundingClientRect().height > 0) {
                const rect = view.card.getBoundingClientRect();
                
                if (!view.isVideo) {
                    // Measure the target ONCE (world AABB changes as parts rotate,
                    // which would make the camera pulse). Cache the radius and the
                    // center in the link's LOCAL frame so it still tracks the part
                    // when its link translates, but ignores its spin.
                    if (!view._frame) {
                        const box = new THREE.Box3().setFromObject(view.target);
                        if (box.isEmpty()) return;
                        const centerW = box.getCenter(new THREE.Vector3());
                        view._frame = {
                            radius: Math.max(box.getSize(new THREE.Vector3()).length() * 0.5, 0.02),
                            localCenter: view.target.worldToLocal(centerW.clone())
                        };
                    }
                    const radius = view._frame.radius;
                    const center = view.target.localToWorld(view._frame.localCenter.clone());
                    const keyDir = new THREE.Vector3(2, 4, 3).normalize(); // matches main key light
                    view.camera.position.copy(center).addScaledVector(keyDir, radius * 2.2);
                    view.camera.near = Math.max(radius * 0.05, 0.001);
                    view.camera.far  = radius * 50;
                    view.camera.updateProjectionMatrix();
                    view.camera.lookAt(center);

                    this.renderer.setViewport(rect.left, innerHeight - rect.bottom, rect.width, rect.height);
                    this.renderer.setScissor(rect.left, innerHeight - rect.bottom, rect.width, rect.height);
                    this.renderer.render(scene, view.camera);
                }
            }
        });
        this.renderer.setScissorTest(false);
    }
}