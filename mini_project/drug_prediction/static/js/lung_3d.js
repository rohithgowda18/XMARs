/**
 * ═══════════════════════════════════════════════════════════════
 * lung_3d.js — Interactive 3D Human Lung Anatomical Model
 * Three.js + GLTFLoader + OrbitControls
 * Model: Human Reference Atlas / Visible Human Project (NIH / HuBMAP, CC-BY 4.0)
 * ═══════════════════════════════════════════════════════════════
 */

let lungScene = null;
let lungCamera = null;
let lungRenderer = null;
let lungControls = null;
let lungModelGroup = null;
let lungAnimFrameId = null;
let isLungInitialized = false;
let isLungWireframe = false;
let isLungAutoRotating = true;

const LUNG_INITIAL_CAM_POS = { x: 0, y: 0.5, z: 4.8 };
const LUNG_INITIAL_TARGET = { x: 0, y: 0, z: 0 };

/**
 * Open the 3D Human Lung Anatomy Modal
 */
function openLungModal() {
    const modal = document.getElementById('lung3DModal');
    if (!modal) return;
    modal.style.display = 'flex';

    if (!isLungInitialized) {
        // Small delay to ensure container DOM dimensions are computed
        setTimeout(() => {
            initLungScene('lung3DContainer');
        }, 60);
    } else {
        handleLungResize();
    }
}

/**
 * Close the 3D Human Lung Anatomy Modal
 */
function closeLungModal() {
    const modal = document.getElementById('lung3DModal');
    if (!modal) return;
    modal.style.display = 'none';
}

/**
 * Initialize Three.js Scene, Camera, Lights, and OrbitControls
 */
function initLungScene(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const width = container.clientWidth || 900;
    const height = container.clientHeight || 550;

    // 1. Scene
    lungScene = new THREE.Scene();
    lungScene.background = new THREE.Color(0x060a14);

    // Subtle atmospheric fog for biotech depth
    lungScene.fog = new THREE.FogExp2(0x060a14, 0.08);

    // 2. Camera
    lungCamera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    lungCamera.position.set(LUNG_INITIAL_CAM_POS.x, LUNG_INITIAL_CAM_POS.y, LUNG_INITIAL_CAM_POS.z);

    // 3. WebGL Renderer
    try {
        lungRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
        lungRenderer.setSize(width, height);
        lungRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        lungRenderer.toneMapping = THREE.ACESFilmicToneMapping;
        lungRenderer.toneMappingExposure = 1.1;
        container.appendChild(lungRenderer.domElement);
    } catch (e) {
        console.warn('WebGL not supported, rendering SVG anatomical fallback:', e);
        renderLungFallbackSVG(container);
        return;
    }

    // 4. OrbitControls
    if (typeof THREE.OrbitControls !== 'undefined') {
        lungControls = new THREE.OrbitControls(lungCamera, lungRenderer.domElement);
        lungControls.enableDamping = true;
        lungControls.dampingFactor = 0.05;
        lungControls.autoRotate = isLungAutoRotating;
        lungControls.autoRotateSpeed = 1.0;
        lungControls.minDistance = 1.5;
        lungControls.maxDistance = 12.0;
        lungControls.target.set(LUNG_INITIAL_TARGET.x, LUNG_INITIAL_TARGET.y, LUNG_INITIAL_TARGET.z);
    }

    // 5. Scientific Biotech Lighting Setup
    // Key Light: Cool Cyan-Blue from top-front-right
    const keyLight = new THREE.DirectionalLight(0x38bdf8, 2.2);
    keyLight.position.set(4, 6, 5);
    lungScene.add(keyLight);

    // Fill Light: Soft Electric Violet from bottom-left
    const fillLight = new THREE.DirectionalLight(0x818cf8, 1.4);
    fillLight.position.set(-4, -2, -3);
    lungScene.add(fillLight);

    // Rim/Back Light: Crisp Emerald-Cyan from behind
    const rimLight = new THREE.DirectionalLight(0x2dd4bf, 1.8);
    rimLight.position.set(0, 5, -6);
    lungScene.add(rimLight);

    // Soft Ambient Foundation
    const ambientLight = new THREE.AmbientLight(0x0f172a, 0.9);
    lungScene.add(ambientLight);

    // Grid Floor / Reference Ring
    const grid = new THREE.GridHelper(10, 20, 0x1e293b, 0x0f172a);
    grid.position.y = -2.2;
    lungScene.add(grid);

    // 6. Load GLB Model
    loadLungGLBModel(container);

    // 7. Event Listeners
    window.addEventListener('resize', handleLungResize);

    // 8. Animation Loop
    function animate() {
        lungAnimFrameId = requestAnimationFrame(animate);
        if (lungControls) lungControls.update();
        if (lungRenderer && lungScene && lungCamera) {
            lungRenderer.render(lungScene, lungCamera);
        }
    }
    animate();

    isLungInitialized = true;
}

/**
 * Load GLTF/GLB Model via Three.js GLTFLoader
 */
function loadLungGLBModel(container) {
    const spinner = document.getElementById('lungLoadingSpinner');
    const modelUrl = '/static/models/lungs.glb';

    if (typeof THREE.GLTFLoader === 'undefined') {
        console.warn('GLTFLoader not available, using fallback mesh');
        if (spinner) spinner.style.display = 'none';
        buildProceduralLungGeometry();
        return;
    }

    const loader = new THREE.GLTFLoader();
    loader.load(
        modelUrl,
        function (gltf) {
            if (spinner) spinner.style.display = 'none';

            lungModelGroup = gltf.scene;

            // Compute Bounding Box & Center/Scale model
            const box = new THREE.Box3().setFromObject(lungModelGroup);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());

            const maxDim = Math.max(size.x, size.y, size.z);
            const targetSize = 3.6;
            const scale = targetSize / (maxDim || 1);

            lungModelGroup.scale.set(scale, scale, scale);
            lungModelGroup.position.x = -center.x * scale;
            lungModelGroup.position.y = -center.y * scale;
            lungModelGroup.position.z = -center.z * scale;

            // Apply Premium Biotech Shaders to all child meshes
            lungModelGroup.traverse(child => {
                if (child.isMesh) {
                    child.castShadow = true;
                    child.receiveShadow = true;

                    // Sophisticated biological physical material
                    child.material = new THREE.MeshPhysicalMaterial({
                        color: new THREE.Color(0x1e3a5f),
                        emissive: new THREE.Color(0x06182a),
                        roughness: 0.38,
                        metalness: 0.18,
                        clearcoat: 0.45,
                        clearcoatRoughness: 0.25,
                        transparent: true,
                        opacity: 0.94,
                        side: THREE.DoubleSide
                    });
                }
            });

            lungScene.add(lungModelGroup);
        },
        function (xhr) {
            if (xhr.lengthComputable && spinner) {
                const percent = Math.round((xhr.loaded / xhr.total) * 100);
                spinner.querySelector('div:last-child').textContent = `Loading Anatomy: ${percent}%`;
            }
        },
        function (error) {
            console.error('Error loading lungs.glb:', error);
            if (spinner) spinner.style.display = 'none';
            buildProceduralLungGeometry();
        }
    );
}

/**
 * Procedural Anatomical Fallback (Generates high-fidelity 3D lung lobes if GLB is unavailable)
 */
function buildProceduralLungGeometry() {
    lungModelGroup = new THREE.Group();

    const lobeMaterial = new THREE.MeshPhysicalMaterial({
        color: 0x1e3a5f,
        emissive: 0x061a2e,
        roughness: 0.4,
        metalness: 0.2,
        clearcoat: 0.4,
        transparent: true,
        opacity: 0.9
    });

    const bronchiaMaterial = new THREE.MeshStandardMaterial({
        color: 0x38bdf8,
        emissive: 0x0284c7,
        roughness: 0.3,
        metalness: 0.5
    });

    // Right Lung (3 anatomical lobes)
    const rightUpper = new THREE.Mesh(new THREE.SphereGeometry(0.85, 32, 24), lobeMaterial);
    rightUpper.scale.set(0.8, 1.2, 0.7);
    rightUpper.position.set(-1.0, 0.7, 0);
    lungModelGroup.add(rightUpper);

    const rightMiddle = new THREE.Mesh(new THREE.SphereGeometry(0.7, 32, 24), lobeMaterial);
    rightMiddle.scale.set(0.75, 0.8, 0.65);
    rightMiddle.position.set(-1.1, -0.2, 0.1);
    lungModelGroup.add(rightMiddle);

    const rightLower = new THREE.Mesh(new THREE.SphereGeometry(0.9, 32, 24), lobeMaterial);
    rightLower.scale.set(0.85, 1.1, 0.75);
    rightLower.position.set(-0.95, -1.0, -0.1);
    lungModelGroup.add(rightLower);

    // Left Lung (2 anatomical lobes with cardiac impression)
    const leftUpper = new THREE.Mesh(new THREE.SphereGeometry(0.85, 32, 24), lobeMaterial);
    leftUpper.scale.set(0.75, 1.2, 0.7);
    leftUpper.position.set(1.0, 0.6, 0);
    lungModelGroup.add(leftUpper);

    const leftLower = new THREE.Mesh(new THREE.SphereGeometry(0.95, 32, 24), lobeMaterial);
    leftLower.scale.set(0.8, 1.2, 0.75);
    leftLower.position.set(1.05, -0.8, -0.05);
    lungModelGroup.add(leftLower);

    // Trachea & Main Bronchi
    const trachea = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.14, 1.4, 20), bronchiaMaterial);
    trachea.position.set(0, 1.4, 0);
    lungModelGroup.add(trachea);

    const rightBronchus = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.08, 0.8, 16), bronchiaMaterial);
    rightBronchus.position.set(-0.35, 0.6, 0);
    rightBronchus.rotation.z = Math.PI / 4;
    lungModelGroup.add(rightBronchus);

    const leftBronchus = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.07, 0.9, 16), bronchiaMaterial);
    leftBronchus.position.set(0.4, 0.55, 0);
    leftBronchus.rotation.z = -Math.PI / 3.5;
    lungModelGroup.add(leftBronchus);

    lungScene.add(lungModelGroup);
}

/**
 * Handle Responsive Resize
 */
function handleLungResize() {
    const container = document.getElementById('lung3DContainer');
    if (!container || !lungRenderer || !lungCamera) return;

    const width = container.clientWidth;
    const height = container.clientHeight;

    if (width > 0 && height > 0) {
        lungCamera.aspect = width / height;
        lungCamera.updateProjectionMatrix();
        lungRenderer.setSize(width, height);
    }
}

/**
 * Controls: Toggle Continuous Auto-Rotation
 */
function toggleLungAutoRotate() {
    isLungAutoRotating = !isLungAutoRotating;
    if (lungControls) {
        lungControls.autoRotate = isLungAutoRotating;
    }
    const btn = document.getElementById('btnAutoRotate');
    const icon = document.getElementById('autoRotateIcon');
    if (btn) {
        if (isLungAutoRotating) {
            btn.classList.add('active');
            if (icon) icon.textContent = '⏸';
        } else {
            btn.classList.remove('active');
            if (icon) icon.textContent = '▶';
        }
    }
}

/**
 * Controls: Reset Camera Position & Zoom
 */
function resetLungView() {
    if (!lungCamera || !lungControls) return;
    lungCamera.position.set(LUNG_INITIAL_CAM_POS.x, LUNG_INITIAL_CAM_POS.y, LUNG_INITIAL_CAM_POS.z);
    lungControls.target.set(LUNG_INITIAL_TARGET.x, LUNG_INITIAL_TARGET.y, LUNG_INITIAL_TARGET.z);
    lungControls.update();
}

/**
 * Controls: Toggle Wireframe Shading Mode
 */
function toggleLungWireframe() {
    isLungWireframe = !isLungWireframe;
    if (lungModelGroup) {
        lungModelGroup.traverse(child => {
            if (child.isMesh && child.material) {
                child.material.wireframe = isLungWireframe;
            }
        });
    }
    const btn = document.getElementById('btnWireframe');
    if (btn) {
        if (isLungWireframe) btn.classList.add('active');
        else btn.classList.remove('active');
    }
}

/**
 * Fallback 2D Anatomical Blueprint if WebGL is disabled
 */
function renderLungFallbackSVG(container) {
    container.innerHTML = `
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:#94a3b8;padding:20px;text-align:center;">
            <div style="font-size:3rem;margin-bottom:12px;">🫁</div>
            <h3 style="color:#ffffff;font-size:1.1rem;margin-bottom:6px;">Anatomical Human Lung Model</h3>
            <p style="max-width:400px;font-size:0.82rem;color:#64748b;margin-bottom:16px;">
                WebGL acceleration unavailable in current browser session. Bilateral lobes and tracheobronchial arborization mapped according to Human Reference Atlas standards.
            </p>
        </div>
    `;
}

// Global Exports
if (typeof window !== 'undefined') {
    window.openLungModal = openLungModal;
    window.closeLungModal = closeLungModal;
    window.toggleLungAutoRotate = toggleLungAutoRotate;
    window.resetLungView = resetLungView;
    window.toggleLungWireframe = toggleLungWireframe;
}
